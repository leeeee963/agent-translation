import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Eye, EyeOff } from "lucide-react";
import { fetchLLMConfig, saveLLMConfig } from "../api";

interface LLMSettingsProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function LLMSettings({ open, onOpenChange }: LLMSettingsProps) {
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [maskedKey, setMaskedKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setError("");
    setSaved(false);
    setApiKey("");
    setShowKey(false);
    fetchLLMConfig()
      .then((cfg) => {
        setMaskedKey(cfg.api_key_masked);
        setBaseUrl(cfg.base_url);
        setModel(cfg.model);
      })
      .catch(() => setError("加载配置失败"));
  }, [open]);

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const payload: { api_key?: string; base_url?: string; model?: string } = {};
      if (apiKey.trim()) payload.api_key = apiKey.trim();
      if (baseUrl.trim()) payload.base_url = baseUrl.trim();
      if (model.trim()) payload.model = model.trim();
      await saveLLMConfig(payload);
      setSaved(true);
      if (apiKey.trim()) {
        // update masked display
        const k = apiKey.trim();
        setMaskedKey(k.length > 4 ? "•".repeat(k.length - 4) + k.slice(-4) : k);
        setApiKey("");
        setShowKey(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>API 与模型配置</DialogTitle>
          <DialogDescription>
            修改后将在下一个翻译任务中生效
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* API Key */}
          <div className="space-y-1">
            <label className="text-sm font-medium">API Key</label>
            <div className="relative">
              <Input
                type={showKey ? "text" : "password"}
                placeholder={maskedKey || "输入新的 API Key"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="pr-10"
              />
              <button
                type="button"
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                onClick={() => setShowKey((v) => !v)}
              >
                {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
            {maskedKey && !apiKey && (
              <p className="text-xs text-gray-400">当前：{maskedKey}（留空则不修改）</p>
            )}
          </div>

          {/* Base URL */}
          <div className="space-y-1">
            <label className="text-sm font-medium">API 地址</label>
            <Input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.poe.com/v1"
            />
          </div>

          {/* Model */}
          <div className="space-y-1">
            <label className="text-sm font-medium">模型</label>
            <Input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="GPT-4o"
            />
            <p className="text-xs text-gray-400">对所有任务（术语提取、翻译等）统一生效</p>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}
          {saved && <p className="text-sm text-green-600">已保存</p>}
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            关闭
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "保存中..." : "保存"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
