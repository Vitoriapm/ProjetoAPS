import 'dart:convert';

import 'package:ecopulse/data/api_client.dart';
import 'package:ecopulse/models/position_point.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'core_fakes.dart';

void main() {
  test(
    'POST uses the shared JSON contract and Bearer installation session',
    () async {
      final report = fixtureReport(pending: true);
      final requests = <http.Request>[];
      final client = ApiClient(
        client: MockClient((request) async {
          requests.add(request);
          if (request.url.path == '/v1/sessoes') {
            expect(jsonDecode(request.body), {
              'installation_id': 'installation',
            });
            return http.Response(jsonEncode({'access_token': 'session'}), 200);
          }
          expect(request.url.path, '/v1/relatos');
          expect(request.headers['Authorization'], 'Bearer session');
          expect(jsonDecode(request.body), report.toJson());
          return http.Response(
            jsonEncode(report.confirmed().toLocalJson()),
            201,
          );
        }),
      );
      client.configure(
        baseUrl: 'http://localhost:8000',
        installationId: 'installation',
      );
      expect((await client.postReport(report)).id, report.id);
      expect(requests.length, 2);
      client.dispose();
    },
  );

  test(
    'GeoJSON incidents parse coordinates and version intact',
    () async {
      final fixture = fixtureIncident(version: 3);
      final client = ApiClient(
        client: MockClient((request) async {
          expect(request.url.queryParameters['latitude'], '-21.1775');
          return http.Response(
            jsonEncode({
              'type': 'FeatureCollection',
              'features': [fixture.toFeature()],
            }),
            200,
          );
        }),
      );
      client.configure(
        baseUrl: 'http://localhost:8000',
        installationId: 'test',
      );
      final result = await client.getIncidents(
        const PositionPoint(latitude: -21.1775, longitude: -47.8103),
      );
      expect(result.single.version, 3);
      expect(result.single.polygons, fixture.polygons);
      expect(result.single.isDemo, true);
      client.dispose();
    },
  );

  test(
    '503 route error is readable and does not yield a fabricated route',
    () async {
      final client = ApiClient(
        client: MockClient(
          (request) async => request.url.path == '/v1/sessoes'
              ? http.Response('{"access_token":"token"}', 200)
              : http.Response(
                  '{"detail":"Provedor de rotas não configurado."}',
                  503,
                  headers: {'content-type': 'application/json; charset=utf-8'},
                ),
        ),
      );
      client.configure(
        baseUrl: 'http://localhost:8000',
        installationId: 'test',
      );
      await expectLater(
        client.getRoute(
          origin: const PositionPoint(latitude: -21.17, longitude: -47.81),
          destination: const PositionPoint(latitude: -21.2, longitude: -47.9),
          profile: 'driving-car',
        ),
        throwsA(
          isA<ApiException>().having(
            (error) => error.statusCode,
            'statusCode',
            503,
          ),
        ),
      );
      client.dispose();
    },
  );
}
