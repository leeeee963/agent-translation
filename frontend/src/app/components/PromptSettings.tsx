import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Badge } from "./ui/badge";
import { Info } from "lucide-react";
import { fetchPrompt, savePrompt } from "../api";

interface PromptSettingsProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const PROMPT_VARIABLES = [
  { name: '{target_language}', description: '目标语言' },
  { name: '{source_text}', description: '原文内容' },
  { name: '{glossary_constraints}', description: '术语约束' },
  { name: '{context_hint}', description: '上下文提示' },
];

export function PromptSettings({
  open,
  onOpenChange,
}: PromptSettingsProps) {
  const [editedPrompt, setEditedPrompt] = useState('');
  const [savedPrompt, setSavedPrompt] = useState('');
  const [promptPath, setPromptPath] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [banner, setBanner] = useState<{ type: string; message: string }>({ type: '', message: '' });

  useEffect(() => {
    if (open) {
      loadPrompt();
    }
  }, [open]);

  const loadPrompt = async () => {
    setLoading(true);
    setBanner({ type: '', message: '' });
    try {
      const config = await fetchPrompt();
      setEditedPrompt(config.content);
      setSavedPrompt(config.content);
      setPromptPath(config.path || '');
    } catch (err: unknown) {
      setBanner({ type: 'error', message: err instanceof Error ? err.message : String(err) });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setBanner({ type: '', message: '' });
    try {
      await savePrompt(editedPrompt);
      setSavedPrompt(editedPrompt);
      setBanner({ type: 'success', message: 'Prompt 已保存' });
      setTimeout(() => onOpenChange(false), 800);
    } catch (err: unknown) {
      setBanner({ type: 'error', message: err instanceof Error ? err.message : String(err) });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setEditedPrompt(savedPrompt);
  };

  const promptDirty = editedPrompt !== savedPrompt;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>翻译 Prompt 设置</DialogTitle>
          <DialogDescription>
            配置统一的翻译 Prompt 模板，将应用于所有翻译任务
          </DialogDescription>
        </DialogHeader>

        {banner.message && (
          <div className={`rounded-lg px-4 py-2 text-sm ${
            banner.type === 'error'
              ? 'bg-red-50 text-red-800 border border-red-200'
              : 'bg-green-50 text-green-800 border border-green-200'
          }`}>
            {banner.message}
          </div>
        )}

        <div className="flex-1 overflow-auto space-y-4">
          {/* Variable Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex gap-3">
              <Info className="size-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-blue-900 font-medium mb-2">可用变量</p>
                <div className="space-y-1">
                  {PROMPT_VARIABLES.map((variable) => (
                    <div key={variable.name} className="flex items-center gap-2">
                      <Badge variant="secondary" className="font-mono text-xs">
                        {variable.name}
                      </Badge>
                      <span className="text-sm text-blue-800">{variable.description}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Prompt Editor */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div>
                <label className="font-medium">Prompt 模板</label>
                {promptPath && (
                  <p className="text-xs text-gray-500 mt-0.5">{promptPath}</p>
                )}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={loadPrompt} disabled={loading}>
                  重新加载
                </Button>
                <Button variant="outline" size="sm" onClick={handleReset} disabled={!promptDirty}>
                  恢复默认
                </Button>
              </div>
            </div>
            {loading ? (
              <div className="text-center py-12 text-gray-500">正在加载...</div>
            ) : (
              <Textarea
                value={editedPrompt}
                onChange={(e) => setEditedPrompt(e.target.value)}
                className="min-h-[250px] font-mono text-sm"
                placeholder="输入翻译 Prompt..."
                spellCheck={false}
              />
            )}
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <span>字符数：{editedPrompt.length}</span>
              <span className="text-gray-300">|</span>
              <span>行数：{editedPrompt.split('\n').length}</span>
              {promptDirty && (
                <>
                  <span className="text-gray-300">|</span>
                  <span className="text-amber-600">有未保存修改</span>
                </>
              )}
            </div>
          </div>

          {/* Preview */}
          <div className="space-y-2">
            <label className="font-medium">预览示例</label>
            <div className="bg-gray-50 rounded-lg p-4 text-sm font-mono whitespace-pre-wrap text-gray-700 border">
              {editedPrompt
                .replace('{target_language}', 'English')
                .replace('{source_text}', '这是一个用于验证模板变量的示例文本。')
                .replace('{glossary_constraints}', 'API -> API\nDashboard -> 仪表板')
                .replace('{context_hint}', '产品说明文档')}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-4 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={saving || loading || !promptDirty}>
            {saving ? '保存中...' : '保存设置'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
