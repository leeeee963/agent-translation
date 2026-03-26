import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Textarea } from "./ui/textarea";
import { Badge } from "./ui/badge";
import { Info } from "lucide-react";
import type { Language } from "../types/translation";

interface PromptEditStepProps {
  promptValue: string;
  savedPromptValue: string;
  promptPath: string;
  loading: boolean;
  onPromptChange: (value: string) => void;
  onSave: () => void;
  onReload: () => void;
  onStartTranslation: () => void;
  submitting: boolean;
  selectedLanguages: Language[];
}

const PROMPT_VARIABLES = [
  { name: "{source_text}", description: "原文内容" },
  { name: "{target_language}", description: "目标语言" },
  { name: "{glossary_constraints}", description: "术语约束" },
  { name: "{context_hint}", description: "上下文提示" },
];

export function PromptEditStep({
  promptValue,
  savedPromptValue,
  promptPath,
  loading,
  onPromptChange,
  onSave,
  onReload,
  onStartTranslation,
  submitting,
  selectedLanguages,
}: PromptEditStepProps) {
  const promptDirty = promptValue !== savedPromptValue;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">统一翻译 Prompt</h2>
        <p className="text-gray-600">查看并编辑翻译 Prompt，修改后对后续新任务生效</p>
      </div>

      {/* Info Card */}
      <Card className="p-4 bg-blue-50 border-blue-200">
        <div className="flex gap-3">
          <Info className="size-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-blue-900 font-medium mb-2">Prompt 变量说明</p>
            <div className="space-y-1">
              {PROMPT_VARIABLES.map((v) => (
                <div key={v.name} className="flex items-center gap-2">
                  <Badge variant="secondary" className="font-mono text-xs">{v.name}</Badge>
                  <span className="text-sm text-blue-800">{v.description}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* Prompt Editor */}
      <Card className="p-6">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <label className="font-medium">翻译 Prompt 模板</label>
              <p className="text-xs text-gray-500 mt-1">{promptPath || "config/prompts/translator_unified.md"}</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={onReload} disabled={loading}>
                重新加载
              </Button>
              <Button variant="outline" size="sm" onClick={onSave} disabled={loading || !promptDirty}>
                保存修改
              </Button>
            </div>
          </div>

          <Textarea
            value={promptValue}
            onChange={(e) => onPromptChange(e.target.value)}
            className="min-h-[300px] font-mono text-sm"
            placeholder="统一 Prompt 内容..."
            spellCheck={false}
          />

          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span>字符数：{promptValue.length}</span>
            <span className="text-gray-300">|</span>
            <span>行数：{promptValue.split("\n").length}</span>
            {promptDirty && (
              <>
                <span className="text-gray-300">|</span>
                <span className="text-amber-600">有未保存修改</span>
              </>
            )}
          </div>
        </div>
      </Card>

      {/* Preview */}
      <Card className="p-6">
        <h3 className="font-medium mb-3">预览示例</h3>
        <div className="bg-gray-50 rounded p-4 text-sm font-mono whitespace-pre-wrap text-gray-700">
          {promptValue
            .replace("{target_language}", selectedLanguages[0]?.name || "English")
            .replace("{source_text}", "这是一个用于验证模板变量的示例文本。")
            .replace("{glossary_constraints}", "API -> API\nDashboard -> 仪表板")
            .replace("{context_hint}", "产品说明文档")}
        </div>
      </Card>

      {/* Actions */}
      <div className="flex justify-end pt-4">
        <Button onClick={onStartTranslation} disabled={submitting || !promptValue.trim()} size="lg">
          {submitting ? "任务提交中..." : promptDirty ? "保存并开始翻译" : "开始翻译"}
        </Button>
      </div>
    </div>
  );
}
