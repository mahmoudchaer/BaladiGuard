import * as SecureStore from 'expo-secure-store';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

import { appConfig } from '@/services/config';
import { getAuthHeaders } from '@/services/api/http';

const DEVICE_ID_KEY = 'baladiguard.pushDeviceId';

async function deviceId(): Promise<string> {
  const existing = await SecureStore.getItemAsync(DEVICE_ID_KEY);
  if (existing) return existing;
  const created = `device_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  await SecureStore.setItemAsync(DEVICE_ID_KEY, created);
  return created;
}

export async function registerPushDevice(accessToken: string, channelName: string): Promise<void> {
  if (Platform.OS === 'web')
    throw new Error('Push notifications require a physical mobile device.');
  const Notifications = await import('expo-notifications');
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('ticket-updates', {
      name: channelName,
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }
  const current = await Notifications.getPermissionsAsync();
  const permission = current.granted ? current : await Notifications.requestPermissionsAsync();
  if (!permission.granted)
    throw new Error(
      'Notification permission was not granted. Enable it in device settings and try again.',
    );
  const projectId = Constants.easConfig?.projectId;
  const token = (await Notifications.getExpoPushTokenAsync(projectId ? { projectId } : undefined))
    .data;
  const response = await fetch(`${appConfig.apiBaseUrl}/citizen/me/push-devices`, {
    method: 'PUT',
    headers: { ...getAuthHeaders(accessToken), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      deviceId: await deviceId(),
      token,
      platform: Platform.OS,
      appEnvironment:
        appConfig.appEnv === 'local' || appConfig.appEnv === 'test'
          ? 'development'
          : appConfig.appEnv,
    }),
  });
  if (!response.ok) throw new Error('Unable to register this device for notifications.');
}

export async function unregisterPushDevice(accessToken: string): Promise<void> {
  const id = await SecureStore.getItemAsync(DEVICE_ID_KEY);
  if (!id) return;
  await fetch(`${appConfig.apiBaseUrl}/citizen/me/push-devices/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: getAuthHeaders(accessToken),
  });
}
