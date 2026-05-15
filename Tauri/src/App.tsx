import { FormEvent, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

type PortRecord = {
  protocol: string;
  state: string;
  pid: number | null;
  processName: string;
  occupancyType: string;
  canKill: boolean;
};

type InspectPortResponse = {
  port: number;
  records: PortRecord[];
  message: string;
};

const quickPorts = [80, 443, 3306, 5432, 6379, 8080];

export function App() {
  const [port, setPort] = useState("80");
  const [records, setRecords] = useState<PortRecord[]>([]);
  const [message, setMessage] = useState("输入端口后开始查询");
  const [isLoading, setIsLoading] = useState(false);

  async function inspectPort(nextPort = port) {
    const parsed = Number(nextPort);
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
      setMessage("请输入 1-65535 之间的有效端口");
      setRecords([]);
      return;
    }

    setIsLoading(true);
    setMessage(`正在查询端口 ${parsed}...`);

    try {
      const result = await invoke<InspectPortResponse>("inspect_port", { port: parsed });
      setRecords(result.records);
      setMessage(result.message);
    } catch (error) {
      setRecords([]);
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsLoading(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void inspectPort();
  }

  function chooseQuickPort(nextPort: number) {
    const value = String(nextPort);
    setPort(value);
    void inspectPort(value);
  }

  return (
    <main className="app-shell">
      <section className="toolbar">
        <div>
          <h1>PortClear</h1>
          <p>端口占用诊断与释放工具</p>
        </div>
        <span className="status-pill">Tauri 版本</span>
      </section>

      <section className="query-panel">
        <form className="query-form" onSubmit={handleSubmit}>
          <label htmlFor="port">端口号</label>
          <input
            id="port"
            value={port}
            inputMode="numeric"
            onChange={(event) => setPort(event.target.value)}
            placeholder="例如 8080"
          />
          <button type="submit" disabled={isLoading}>
            {isLoading ? "查询中" : "查询"}
          </button>
        </form>

        <div className="quick-ports" aria-label="常用端口">
          {quickPorts.map((item) => (
            <button key={item} type="button" onClick={() => chooseQuickPort(item)}>
              {item}
            </button>
          ))}
        </div>
      </section>

      <section className="results">
        <div className="results-header">
          <h2>查询结果</h2>
          <span>{message}</span>
        </div>

        <div className="table" role="table" aria-label="端口占用结果">
          <div className="table-row table-head" role="row">
            <span>协议</span>
            <span>状态</span>
            <span>PID</span>
            <span>进程</span>
            <span>类型</span>
            <span>操作</span>
          </div>

          {records.length === 0 ? (
            <div className="empty-state">暂无记录</div>
          ) : (
            records.map((record, index) => (
              <div className="table-row" role="row" key={`${record.pid}-${index}`}>
                <span>{record.protocol}</span>
                <span>{record.state}</span>
                <span>{record.pid ?? "-"}</span>
                <strong>{record.processName}</strong>
                <span>{record.occupancyType}</span>
                <button type="button" disabled={!record.canKill}>
                  {record.canKill ? "终止" : "不可操作"}
                </button>
              </div>
            ))
          )}
        </div>
      </section>
    </main>
  );
}
