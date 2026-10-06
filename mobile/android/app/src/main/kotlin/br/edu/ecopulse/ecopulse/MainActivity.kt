package br.edu.ecopulse.ecopulse

import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity

class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                "ecopulse_alertas", "Ocorrências próximas", NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Avisos de ocorrências ambientais na área selecionada."
            }
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }
}
