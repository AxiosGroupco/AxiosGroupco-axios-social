package co.axiosgroup.marcadorsonido;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.content.res.AssetFileDescriptor;
import android.media.AudioAttributes;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
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
 * PLAY con "--ez bajar true" baja al mínimo el volumen de la llamada (el tono de espera)
 * mientras suena la música; cualquier otra acción lo devuelve a como estaba.
 */
public class Sonido extends Service implements MediaPlayer.OnCompletionListener, TextToSpeech.OnInitListener {
    private static final String CANAL = "sonido";
    private MediaPlayer mp;
    private final List<String> cola = new ArrayList<>();
    private float vol = 0.25f;
    private TextToSpeech voz;
    private boolean vozLista;
    private String pendiente;
    // Volumen de llamada: 0 = llamada normal, 6 = llamada por audífonos Bluetooth.
    private static final int[] FLUJOS_LLAMADA = {AudioManager.STREAM_VOICE_CALL, 6};
    private final Handler reloj = new Handler(Looper.getMainLooper());
    private final Runnable reaplicar = new Runnable() {
        @Override
        public void run() {
            bajarLlamada();
        }
    };

    // Cierre automático: sin cable USB, o si el computador lleva 10 minutos sin dar órdenes.
    private static final long SIN_ORDENES_MS = 10 * 60 * 1000;
    private static final String USB_ESTADO = "android.hardware.usb.action.USB_STATE";
    private final Runnable apagar = new Runnable() {
        @Override
        public void run() {
            cerrar();
        }
    };
    private final BroadcastReceiver cable = new BroadcastReceiver() {
        @Override
        public void onReceive(Context c, Intent i) {
            if (Intent.ACTION_POWER_DISCONNECTED.equals(i.getAction())
                    || (USB_ESTADO.equals(i.getAction()) && !i.getBooleanExtra("connected", true))) {
                cerrar();
            }
        }
    };

    @Override
    public void onCreate() {
        super.onCreate();
        IntentFilter f = new IntentFilter(Intent.ACTION_POWER_DISCONNECTED);
        f.addAction(USB_ESTADO);
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(cable, f, Context.RECEIVER_EXPORTED);
        } else {
            registerReceiver(cable, f);
        }
    }

    private void cerrar() {
        restaurarLlamada();
        stopForeground(true);
        stopSelf();
    }

    @Override
    public IBinder onBind(Intent i) {
        return null;
    }

    @Override
    public int onStartCommand(Intent i, int flags, int id) {
        primerPlano();
        reloj.removeCallbacks(apagar);
        reloj.postDelayed(apagar, SIN_ORDENES_MS);
        String a = i == null ? null : i.getAction();
        try {
            if ("PLAY".equals(a)) {
                vol = Math.max(0, Math.min(100, i.getIntExtra("vol", 25))) / 100f;
                if (i.getBooleanExtra("bajar", false)) {
                    bajarLlamada();
                    reloj.postDelayed(reaplicar, 1500);  // por si el celular lo reajusta al empezar a marcar
                } else {
                    restaurarLlamada();
                }
                tocar();
            } else if ("PAUSE".equals(a)) {
                restaurarLlamada();
                pausar();
            } else if ("SAY".equals(a)) {
                restaurarLlamada();
                pausar();
                decir(new String(Base64.decode(i.getStringExtra("t"), Base64.URL_SAFE), "UTF-8"));
            } else if ("STOP".equals(a)) {
                cerrar();
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

    // ------------------------------------------------------------ volumen de la llamada

    private SharedPreferences memoria() {
        return getSharedPreferences("volumen", MODE_PRIVATE);
    }

    /** Baja al mínimo el volumen de la llamada y recuerda (aunque se cierre la app) cuánto había. */
    private void bajarLlamada() {
        AudioManager am = (AudioManager) getSystemService(AUDIO_SERVICE);
        SharedPreferences m = memoria();
        for (int f : FLUJOS_LLAMADA) {
            try {
                if (!m.contains("v" + f)) m.edit().putInt("v" + f, am.getStreamVolume(f)).commit();
                int minimo = Build.VERSION.SDK_INT >= 28 ? am.getStreamMinVolume(f) : 1;
                am.setStreamVolume(f, minimo, 0);
            } catch (Exception e) {
                // algunos celulares no dejan tocar el volumen Bluetooth: se ignora
            }
        }
    }

    private void restaurarLlamada() {
        reloj.removeCallbacks(reaplicar);
        AudioManager am = (AudioManager) getSystemService(AUDIO_SERVICE);
        SharedPreferences m = memoria();
        for (int f : FLUJOS_LLAMADA) {
            try {
                if (m.contains("v" + f)) {
                    am.setStreamVolume(f, m.getInt("v" + f, am.getStreamVolume(f)), 0);
                    m.edit().remove("v" + f).commit();
                }
            } catch (Exception e) {
                // igual que arriba
            }
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
        reloj.removeCallbacks(apagar);
        try {
            unregisterReceiver(cable);
        } catch (Exception e) {
            // ya no estaba registrado
        }
        restaurarLlamada();
        soltar();
        if (voz != null) voz.shutdown();
        super.onDestroy();
        android.os.Process.killProcess(android.os.Process.myPid());  // no dejar la aplicación abierta
    }
}
