import 'package:flutter/material.dart';

import '../state/report_controller.dart';
import 'report_style.dart';

class ConnectionSheet extends StatefulWidget {
  const ConnectionSheet({super.key, required this.controller});
  final ReportController controller;

  @override
  State<ConnectionSheet> createState() => _ConnectionSheetState();
}

class _ConnectionSheetState extends State<ConnectionSheet> {
  late final TextEditingController _address;
  String? _addressError;

  @override
  void initState() {
    super.initState();
    _address = TextEditingController(text: widget.controller.apiBaseUrl);
  }

  @override
  void dispose() {
    _address.dispose();
    super.dispose();
  }

  void _save() {
    final value = _address.text.trim();
    final uri = Uri.tryParse(value);
    if (uri == null ||
        !uri.hasAuthority ||
        !{'http', 'https'}.contains(uri.scheme)) {
      setState(
        () => _addressError =
            'Use um endereço começando com http:// ou https://.',
      );
      return;
    }
    Navigator.pop(context, value);
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.controller,
    builder: (context, _) => SafeArea(
      child: SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(
          24,
          0,
          24,
          MediaQuery.viewInsetsOf(context).bottom + 24,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Conectar à apresentação',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            const Text(
              'Use o endereço do computador que compartilha os relatos. O celular e o computador precisam estar na mesma rede Wi-Fi.',
              style: TextStyle(fontSize: 13, height: 1.5),
            ),
            const SizedBox(height: 18),
            TextField(
              controller: _address,
              keyboardType: TextInputType.url,
              autocorrect: false,
              onSubmitted: (_) => _save(),
              decoration: InputDecoration(
                labelText: 'Endereço do servidor',
                hintText: 'http://192.168.0.10:8000',
                helperText:
                    'Informe o endereço e a porta mostrados no computador.',
                helperMaxLines: 2,
                errorText: _addressError,
                errorMaxLines: 2,
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _save,
                child: const Text('Salvar e conectar'),
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              'Notificações no aparelho',
              style: TextStyle(fontSize: 12, color: Color(0xFF657167)),
            ),
            const SizedBox(height: 4),
            Text(
              widget.controller.pushStatus,
              style: const TextStyle(fontSize: 13),
            ),
            if (widget.controller.pushReceipt != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  widget.controller.pushReceipt!,
                  style: const TextStyle(fontSize: 13),
                ),
              ),
            if (widget.controller.lastUpdatedAt != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(
                  'Última atualização: ${shortDate(widget.controller.lastUpdatedAt!)}',
                  style: const TextStyle(fontSize: 12),
                ),
              ),
            const SizedBox(height: 12),
            const Divider(),
            const Text(
              'EcoPulse • projeto acadêmico de DSD',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 6),
            const Text(
              'Dados de demonstração aparecem como simulação. Sem internet, seus relatos ficam salvos e serão enviados quando a conexão voltar com o app aberto.',
              style: TextStyle(fontSize: 12, height: 1.5),
            ),
          ],
        ),
      ),
    ),
  );
}
