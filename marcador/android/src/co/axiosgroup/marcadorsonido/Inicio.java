package co.axiosgroup.marcadorsonido;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

/** Pantalla informativa: la aplicación no se usa a mano. */
public class Inicio extends Activity {
    @Override
    protected void onCreate(Bundle estado) {
        super.onCreate(estado);
        TextView t = new TextView(this);
        t.setPadding(48, 96, 48, 48);
        t.setTextSize(18);
        t.setText("Marcador Axios Sonido\n\nEsta aplicación pone la música y los mensajes de voz "
                + "mientras usa Marcador Axios en el computador.\n\nNo hay que abrirla ni configurar "
                + "nada: el computador la controla por el cable USB.");
        setContentView(t);
    }
}
