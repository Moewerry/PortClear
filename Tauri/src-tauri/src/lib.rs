use serde::Serialize;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct PortRecord {
    protocol: String,
    state: String,
    pid: Option<u32>,
    process_name: String,
    occupancy_type: String,
    can_kill: bool,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct InspectPortResponse {
    port: u16,
    records: Vec<PortRecord>,
    message: String,
}

#[tauri::command]
fn inspect_port(port: u16) -> InspectPortResponse {
    InspectPortResponse {
        port,
        records: Vec::new(),
        message: format!("端口 {port} 查询功能待接入系统检测逻辑"),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![inspect_port])
        .run(tauri::generate_context!())
        .expect("failed to run PortClear");
}
