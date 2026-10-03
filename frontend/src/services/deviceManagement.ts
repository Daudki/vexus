import { apiRequest } from "./api";

export type ManagedDeviceStatus =
  | "pending_enrollment"
  | "active"
  | "revoked";

export type DeviceActionType =
  | "status_check"
  | "inventory_sync"
  | "service_restart"
  | "reboot"
  | "isolate";

export type DeviceTaskStatus =
  | "pending"
  | "completed"
  | "failed"
  | "rejected";

export interface ManagedDevice {
  id: string;
  asset_id: string;
  status: ManagedDeviceStatus;
  last_checkin_at: string | null;
  agent_version: string | null;
  reported_os: string | null;
  created_at: string;
}

export interface EnrollmentIssued {
  device: ManagedDevice;
  enrollment_token: string;
  expires_at: string;
}

export interface DeviceTask {
  id: string;
  managed_device_id: string;
  action_type: DeviceActionType;
  status: DeviceTaskStatus;
  result: string;
  error_message: string;
  created_at: string;
  completed_at: string | null;
}

export interface DeviceTaskCreate {
  action_type: DeviceActionType;
  params?: Record<string, unknown>;
  confirm?: boolean;
}

/** Per-action-type policy, mirrored from the backend ACTION_POLICY table
 * (app/device_management/service.py) so the UI can pre-validate
 * before posting (e.g. require confirm=true for reboot/isolate). */
export interface ActionPolicyMeta {
  value: DeviceActionType;
  label: string;
  requiresConfirm: boolean;
  destructive: boolean;
  description: string;
}

export const DEVICE_ACTION_META: ActionPolicyMeta[] = [
  {
    value: "status_check",
    label: "Status check",
    requiresConfirm: false,
    destructive: false,
    description: "Ask the agent to report current device status. Read-only — does not change device state.",
  },
  {
    value: "inventory_sync",
    label: "Inventory sync",
    requiresConfirm: false,
    destructive: false,
    description: "Ask the agent to re-report its inventory (OS, agent version). Read-only.",
  },
  {
    value: "service_restart",
    label: "Service restart",
    requiresConfirm: false,
    destructive: true,
    description: "Restart a named service on the device. State-changing; emits a NetworkEvent on completion.",
  },
  {
    value: "reboot",
    label: "Reboot",
    requiresConfirm: true,
    destructive: true,
    description: "Reboot the device. Irreversible — requires Admin role AND explicit confirm.",
  },
  {
    value: "isolate",
    label: "Isolate",
    requiresConfirm: true,
    destructive: true,
    description: "Network-isolate the device. Irreversible — requires Admin role AND explicit confirm.",
  },
];

export function listDevices(): Promise<ManagedDevice[]> {
  return apiRequest<ManagedDevice[]>("/device-management/devices");
}

export function enrollDevice(assetId: string): Promise<EnrollmentIssued> {
  return apiRequest<EnrollmentIssued>(
    `/device-management/devices/${assetId}/enroll`,
    { method: "POST" },
  );
}

export function revokeDevice(managedDeviceId: string): Promise<ManagedDevice> {
  return apiRequest<ManagedDevice>(
    `/device-management/devices/${managedDeviceId}/revoke`,
    { method: "POST" },
  );
}

export function listDeviceTasks(
  managedDeviceId: string,
): Promise<DeviceTask[]> {
  return apiRequest<DeviceTask[]>(
    `/device-management/devices/${managedDeviceId}/tasks`,
  );
}

export function queueDeviceTask(
  managedDeviceId: string,
  payload: DeviceTaskCreate,
): Promise<DeviceTask> {
  return apiRequest<DeviceTask>(
    `/device-management/devices/${managedDeviceId}/tasks`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}
