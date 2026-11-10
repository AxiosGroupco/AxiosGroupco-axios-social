package co.axiosgroup.marcadorsonido;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.content.res.AssetFileDescriptor;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.os.Build;
import android.os.IBinder;
import android.speech.tts.TextToSpeech;
import android.util.Base64;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/**
 * Reproduce música y dice mensajes en el celular. Lo controla el computador con:
 *   am start-foreground-service -n co.axiosgroup.marcadorsonido/.Sonido -a PLAY --ei vol 25
 * Acciones: PLAY (empieza o continúa), PAUSE, SAY (--es t texto en base64) y STOP.
 */
public class Sonido extends Service implements MediaPlayer.OnCompletionListener, TextToSpeech.OnInitListener {
    private static final String CANAL = "sonido";
    private MediaPlayer mp;
    private final List<String> cola = new ArrayList<>();
    private float vol = 0.25f;
    private TextToSpeech voz;
    private boolean vozLista;
    private String pendiente;

    @Override
    public IBinder onBind(Intent i) {
        return null;
    }

    @Override
    public int onStartCommand(Intent i, int flags, int id) {
        primerPlano();
        String a = i == null ? null : i.getAction();
        try {
            if ("PLAY".equals(a)) {
                vol = Math.max(0, Math.min(100, i.getIntExtra("vol", 25))) / 100f;
                tocar();
            } else if ("PAUSE".equals(a)) {
                pausar();
            } else if ("SAY".equals(a)) {
                pausar();
                decir(new String(Base64.decode(i.getStringExtra("t"), Base64.URL_SAFE), "UTF-8"));
            } else if ("STOP".equals(a)) {
                stopForeground(true);
                stopSelf();
            }
        } catch (Exception e) {
            // Nunca tumbar el servicio por un problema de sonido: el marcado es lo importante.
        }
        return START_NOT_STICKY;
    }

    private void primerPlano() {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        nm.createNotificationChannel(new NotificationChannel(CANAL, "Sonido de Marcador Axios",
                NotificationManager.IMPORTANCE_LOW));
        Notification n = new Notification.Builder(this, CANAL)
                .setContentTitle("Marcador Axios")
                .setContentText("Música mientras timbra")
                .setSmallIcon(android.R.drawable.ic_media_play)
                .build();
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
        } else {
            startForeground(1, n);
        }
    }

    // ------------------------------------------------------------ música

    private boolean abrirOtra() {
        soltar();
        try {
            if (cola.isEmpty()) {
                for (String f : getAssets().list("")) {
                    if (f.endsWith(".mp3")) cola.add(f);
                }
                Collections.shuffle(cola);
            }
            if (cola.isEmpty()) return false;
            AssetFileDescriptor afd = getAssets().openFd(cola.remove(cola.size() - 1));
            mp = new MediaPlayer();
            mp.setAudioAttributes(new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build());
            mp.setDataSource(afd.getFileDescriptor(), afd.getStartOffset(), afd.getLength());
            afd.close();
            mp.prepare();
            mp.setOnCompletionListener(this);
            return true;
        } catch (Exception e) {
            soltar();
            return false;
        }
    }

    private void tocar() {
        if (mp == null && !abrirOtra()) return;
        mp.setVolume(vol, vol);
        if (!mp.isPlaying()) mp.start();
    }

    private void pausar() {
        if (mp != null && mp.isPlaying()) mp.pause();
    }

    @Override
    public void onCompletion(MediaPlayer m) {
        if (abrirOtra()) {
            mp.setVolume(vol, vol);
            mp.start();
        }
    }

    private void soltar() {
        if (mp != null) {
            mp.release();
            mp = null;
        }
    }

    // ------------------------------------------------------------ voz

    private void decir(String texto) {
        if (voz == null) {
            pendiente = texto;
            voz = new TextToSpeech(this, this);
        } else if (vozLista) {
            voz.speak(texto, TextToSpeech.QUEUE_FLUSH, null, "mensaje");
        } else {
            pendiente = texto;
        }
    }

    @Override
    public void onInit(int estado) {
        if (estado != TextToSpeech.SUCCESS) return;
        if (voz.setLanguage(new Locale("es", "CO")) < TextToSpeech.LANG_AVAILABLE) {
            voz.setLanguage(new Locale("es"));
        }
        vozLista = true;
        if (pendiente != null) {
            voz.speak(pendiente, TextToSpeech.QUEUE_FLUSH, null, "mensaje");
            pendiente = null;
        }
    }

    @Override
    public void onDestroy() {
        soltar();
        if (voz != null) voz.shutdown();
        super.onDestroy();
    }
}
