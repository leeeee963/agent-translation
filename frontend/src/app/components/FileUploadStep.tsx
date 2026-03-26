import { useRef, useState } from "react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Upload, File as FileIcon, X, Plus } from "lucide-react";
import type { TranslationFile } from "../types/translation";

interface FileUploadStepProps {
  files: TranslationFile[];
  onAddFiles: (files: FileList) => void;
  onRemoveFile: (id: string) => void;
  onNext: () => void;
  useGlossary: boolean;
  onUseGlossaryChange: (value: boolean) => void;
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function FileUploadStep({ files, onAddFiles, onRemoveFile, onNext, useGlossary, onUseGlossaryChange }: FileUploadStepProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") {
      const related = e.relatedTarget as Node | null;
      if (!related || !e.currentTarget.contains(related)) setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.length) onAddFiles(e.dataTransfer.files);
  };

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">上传文件</h2>
        <p className="text-gray-600">准备待翻译内容，支持批量上传</p>
      </div>

      {/* Upload Area */}
      <Card
        className={`p-12 border-2 border-dashed transition-colors ${dragActive ? "border-blue-500 bg-blue-50" : "border-gray-300"}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center">
            <Upload className="size-8 text-gray-400" />
          </div>
          <div className="text-center">
            <p className="text-sm text-gray-600 mb-2">
              拖拽文件到此处或
              <button className="text-blue-600 hover:underline ml-1" onClick={() => fileInputRef.current?.click()}>
                浏览文件
              </button>
            </p>
            <p className="text-xs text-gray-500">支持 PPTX、DOCX、DOC、SRT、VTT、ASS，可批量选择</p>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={(e) => {
              if (e.target.files?.length) onAddFiles(e.target.files);
              e.target.value = "";
            }}
            className="hidden"
            accept=".pptx,.docx,.doc,.srt,.vtt,.ass,.md,.json,.yaml,.yml,.po,.pot,.xliff,.xlf,.xml,.html,.htm"
          />
        </div>
      </Card>

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h3 className="font-medium">已添加 {files.length} 个文件</h3>
              <span className="text-sm text-gray-500">总大小: {formatFileSize(totalSize)}</span>
            </div>
            <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
              <Plus className="size-4 mr-2" />
              继续添加
            </Button>
          </div>

          <div className="space-y-2">
            {files.map((file) => (
              <Card key={file.id} className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className="w-10 h-10 bg-blue-100 rounded flex items-center justify-center flex-shrink-0">
                      <FileIcon className="size-5 text-blue-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{file.name}</p>
                      <p className="text-sm text-gray-500">{formatFileSize(file.size)}</p>
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => onRemoveFile(file.id)}>
                    <X className="size-4" />
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Mode Selection */}
      <div>
        <h3 className="font-medium mb-3">翻译模式</h3>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => onUseGlossaryChange(false)}
            className={`p-4 rounded-lg border-2 text-left transition-colors ${!useGlossary ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white hover:border-gray-300"}`}
          >
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${!useGlossary ? "border-blue-500" : "border-gray-400"}`}>
                {!useGlossary && <div className="w-2 h-2 rounded-full bg-blue-500" />}
              </div>
              <span className="font-medium text-sm">直接翻译</span>
            </div>
            <p className="text-xs text-gray-500">上传后立即翻译</p>
            <p className="text-xs text-gray-400">适合简单文档</p>
          </button>
          <button
            onClick={() => onUseGlossaryChange(true)}
            className={`p-4 rounded-lg border-2 text-left transition-colors ${useGlossary ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white hover:border-gray-300"}`}
          >
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${useGlossary ? "border-blue-500" : "border-gray-400"}`}>
                {useGlossary && <div className="w-2 h-2 rounded-full bg-blue-500" />}
              </div>
              <span className="font-medium text-sm">术语表模式</span>
            </div>
            <p className="text-xs text-gray-500">AI提取术语候选</p>
            <p className="text-xs text-gray-400">译员审核确认后再翻译</p>
          </button>
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-end pt-4">
        <Button onClick={onNext} disabled={files.length === 0} size="lg">
          下一步：选择语言 ({files.length} 个文件)
        </Button>
      </div>
    </div>
  );
}
