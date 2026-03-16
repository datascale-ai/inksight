import { Platform } from 'react-native';

export type BleProvisionDevice = {
  id: string;
  name: string;
  rssi: number;
  transport: 'ble';
};

export async function getBleAvailability() {
  return {
    supported: Platform.OS === 'ios' || Platform.OS === 'android',
    platform: Platform.OS,
  };
}

export async function scanProvisionDevices() {
  if (Platform.OS !== 'ios' && Platform.OS !== 'android') {
    return [] as BleProvisionDevice[];
  }

  // Placeholder scan result until react-native-ble-plx is wired to hardware firmware.
  return [
    {
      id: 'INKSIGHT-DEMO-01',
      name: 'InkSight Provisioning',
      rssi: -52,
      transport: 'ble',
    },
  ] as BleProvisionDevice[];
}
