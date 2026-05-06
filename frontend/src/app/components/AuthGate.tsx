import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { fetchAuthStatus, login } from "../api";

type Status = "loading" | "not-configured" | "needs-login" | "ok";

interface AuthGateProps {
  children: ReactNode;
}

export function AuthGate({ children }: AuthGateProps) {
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    fetchAuthStatus()
      .then((s) => {
        if (!s.configured) setStatus("not-configured");
        else if (s.authenticated) setStatus("ok");
        else setStatus("needs-login");
      })
      .catch(() => setStatus("needs-login"));
  }, []);

  if (status === "loading") {
    return <div className="size-full" />;
  }

  if (status === "not-configured") {
    return <NotConfiguredScreen />;
  }

  if (status === "needs-login") {
    return <LoginScreen onSuccess={() => setStatus("ok")} />;
  }

  return <>{children}</>;
}

function NotConfiguredScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="max-w-md text-center space-y-3">
        <h1 className="text-xl font-semibold">服务端未配置访问密码</h1>
        <p className="text-sm text-muted-foreground leading-relaxed">
          请在服务端 <code className="px-1 py-0.5 rounded bg-muted">.env</code> 文件中设置{" "}
          <code className="px-1 py-0.5 rounded bg-muted">ACCESS_PASSWORD</code>，然后重启服务。
        </p>
      </div>
    </div>
  );
}

function LoginScreen({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!password) return;
    setLoading(true);
    setError("");
    try {
      await login(password);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6 bg-background">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-5 bg-card border border-border rounded-xl p-6 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_2px_8px_rgba(0,0,0,0.03)]"
      >
        <div className="space-y-1">
          <h1 className="text-lg font-semibold">访问验证</h1>
          <p className="text-sm text-muted-foreground">请输入访问密码以继续</p>
        </div>
        <Input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="访问密码"
          autoFocus
          disabled={loading}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="w-full" disabled={loading || !password}>
          {loading ? "登录中..." : "登录"}
        </Button>
      </form>
    </div>
  );
}
