import { useRef, useState } from "react";
import { Button } from "./ui/button";
import { Upload, FileText, X, Plus } from "lucide-react";
import type { TranslationFile } from "../types/translation";
import { useLanguage } from "../contexts/LanguageContext";

interface FileUploadSectionProps {
  files: TranslationFile[];
  onFilesChange: (files: TranslationFile[]) => void;
}

const VALID_EXTENSIONS = [".pptx", ".srt", ".vtt", ".ass", ".docx", ".doc", ".md", ".json", ".yaml", ".yml", ".po", ".pot", ".xliff", ".xlf", ".xml", ".html", ".htm"];

function getExtension(filename: string) {
  const index = filename.lastIndexOf(".");
  return index >= 0 ? filename.slice(index).toLowerCase() : "";
}

export function FileUploadSection({ files, onFilesChange }: FileUploadSectionProps) {
  const { t } = useLanguage();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      const related = e.relatedTarget as Node | null;
      if (!related || !e.currentTarget.contains(related)) setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFiles(e.target.files);
      e.target.value = "";
    }
  };

  const handleFiles = (fileList: FileList) => {
    const newFiles: TranslationFile[] = [];
    Array.from(fileList).forEach((file) => {
      const ext = getExtension(file.name);
      if (!VALID_EXTENSIONS.includes(ext)) {
        return;
      }
      if (!files.some((f) => f.name === file.name && f.size === file.size)) {
        newFiles.push({
          id: `file-${Date.now()}-${file.name}-${file.size}`,
          name: file.name,
          size: file.size,
          file,
          uploadProgress: 100,
          uploadStatus: 'completed',
        });
      }
    });

    if (newFiles.length) {
      onFilesChange([...files, ...newFiles]);
    }
  };

  const removeFile = (id: string) => {
    onFilesChange(files.filter((file) => file.id !== id));
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const inputElement = (
    <input
      ref={fileInputRef}
      type="file"
      multiple
      onChange={handleChange}
      className="hidden"
      accept=".pptx,.docx,.doc,.srt,.vtt,.ass,.md,.json,.yaml,.yml,.po,.pot,.xliff,.xlf,.xml,.html,.htm"
    />
  );

  // Has files: grid thumbnails
  if (files.length > 0) {
    return (
      <div
        className={`rounded-lg transition-colors ${dragActive ? 'bg-accent' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        {inputElement}
        <div className="grid grid-cols-3 gap-2">
          {files.map((file) => (
            <div key={file.id} className="group relative">
              <div className="w-14 h-16 rounded-md border border-dashed border-border flex flex-col items-center justify-center bg-muted/20 mx-auto">
                <FileText className="w-5 h-5 text-muted-foreground/60 mb-0.5" />
                <span className="text-[8px] font-medium text-muted-foreground uppercase">
                  {getExtension(file.name).replace('.', '')}
                </span>
              </div>
              <button
                onClick={() => removeFile(file.id)}
                className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-muted-foreground/80 text-background flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X className="w-2.5 h-2.5" />
              </button>
              <p className="text-[10px] text-muted-foreground truncate mt-1 px-0.5">{file.name}</p>
            </div>
          ))}
          <div className="flex items-start justify-center">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="w-14 h-16 rounded-md border border-dashed border-border flex items-center justify-center cursor-pointer hover:bg-muted/30 transition-colors"
            >
              <Plus className="w-4 h-4 text-muted-foreground/60" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  // No files: centered vertical drag-drop area
  return (
    <div
      className={`
        h-full flex flex-col items-center justify-center text-center rounded-lg cursor-pointer transition-colors
        ${dragActive
          ? 'bg-accent'
          : 'hover:bg-muted/30'
        }
      `}
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
      onClick={() => fileInputRef.current?.click()}
    >
      {inputElement}
      <Upload className={`w-6 h-6 mb-2 ${dragActive ? 'text-foreground' : 'text-muted-foreground/60'}`} />
      <p className="text-xs text-foreground">{t('upload.dragDrop')}</p>
      <p className="text-[9px] text-muted-foreground mt-1 leading-relaxed px-2">DOCX, PPTX, SRT, VTT, MD,<br/>JSON, YAML, PO, XLIFF, XML, HTML</p>
    </div>
  );
}
