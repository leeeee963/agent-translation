import { useState } from "react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Checkbox } from "./ui/checkbox";
import { Search } from "lucide-react";
import type { Language } from "../types/translation";

interface LanguageSelectionStepProps {
  availableLanguages: Language[];
  selectedCodes: string[];
  onToggle: (code: string) => void;
  loading: boolean;
  onNext: () => void;
}

export function LanguageSelectionStep({
  availableLanguages,
  selectedCodes,
  onToggle,
  loading,
  onNext,
}: LanguageSelectionStepProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredLanguages = availableLanguages.filter((lang) => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return true;
    return lang.name.toLowerCase().includes(q) || lang.code.toLowerCase().includes(q);
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">选择目标语言</h2>
        <p className="text-gray-600">请至少选择一种目标语言</p>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 size-4 text-gray-400" />
        <Input
          placeholder="搜索语言或语言代码"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Selected Count */}
      {selectedCodes.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-800">
            已选择 <span className="font-semibold">{selectedCodes.length}</span> 种语言
          </p>
        </div>
      )}

      {/* Language Grid */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">正在加载语言列表...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredLanguages.map((lang) => {
            const selected = selectedCodes.includes(lang.code);
            return (
              <Card
                key={lang.code}
                className={`p-4 cursor-pointer transition-all ${
                  selected ? "border-blue-500 bg-blue-50" : "hover:border-gray-400"
                }`}
                onClick={() => onToggle(lang.code)}
              >
                <div className="flex items-center gap-3">
                  <Checkbox
                    checked={selected}
                    onCheckedChange={() => onToggle(lang.code)}
                    onClick={(e) => e.stopPropagation()}
                  />
                  <div className="flex-1">
                    <p className="font-medium">{lang.name}</p>
                    <p className="text-xs text-gray-500">{lang.code.toUpperCase()}</p>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {!loading && filteredLanguages.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">未找到匹配的语言</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-end pt-4">
        <Button onClick={onNext} disabled={selectedCodes.length === 0} size="lg">
          下一步：编辑 Prompt
        </Button>
      </div>
    </div>
  );
}
