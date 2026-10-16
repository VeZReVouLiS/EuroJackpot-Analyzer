package io.github.vezrevoulis.eurojackpot;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(ApkInstallerPlugin.class);      // in-app updates (web/android-native/ApkInstallerPlugin.java)
        super.onCreate(savedInstanceState);
    }
}
