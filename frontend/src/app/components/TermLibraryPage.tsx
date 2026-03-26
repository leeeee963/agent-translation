import { useState, useEffect, useCallback } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "./ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import type { LibraryDomain, LibraryTerm, Language } from "../types/translation";
import {
  fetchLibraryDomains,
  createLibraryDomain,
  deleteLibraryDomain,
  fetchLibraryTerms,
  createLibraryTerm,
  updateLibraryTerm,
  deleteLibraryTerm,
  deleteLibraryTermsBatch,
  importLibraryTerms,
  getExportUrl,
  fetchLanguages,
} from "../api";
import {
  Plus,
  Trash2,
  Search,
  Upload,
  Download,
  LibraryBig,
  ArrowLeft,
  CheckCircle2,
  X,
  Columns,
} from "lucide-react";
import { Link } from "react-router";
import { useLanguage } from "../contexts/LanguageContext";

const PAGE_SIZE = 50;

const STRATEGY_LABELS: Record<string, string> = {
  hard: "刚性翻译",
  keep_original: "保留原文",
  skip: "跳过",
};

export function TermLibraryPage() {
  const { t } = useLanguage();
  return (
    <div className="h-screen bg-muted/50 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="bg-card border-b border-border flex-shrink-0">
        <div className="max-w-[1600px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Link to="/">
                <Button variant="ghost" size="sm">
                  <ArrowLeft className="size-4 mr-1" />
                  {t('library.back')}
                </Button>
              </Link>
              <LibraryBig className="size-6 text-foreground" />
              <h1 className="text-2xl font-semibold">{t('library.title')}</h1>
            </div>
          </div>
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        <TermLibraryContent />
      </div>
    </div>
  );
}

export function TermLibraryContent() {
  const { t, language } = useLanguage();
  const domainName = (d: LibraryDomain) => (language === 'zh' ? d.name_zh : d.name_en) || d.name;
  const domainDesc = (d: LibraryDomain) => (language === 'zh' ? d.description_zh : d.description) || d.description;

  const [domains, setDomains] = useState<LibraryDomain[]>([]);
  const [selectedDomainId, setSelectedDomainId] = useState<number | null>(null);
  const [terms, setTerms] = useState<LibraryTerm[]>([]);
  const [totalTerms, setTotalTerms] = useState(0);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [selectedTermIds, setSelectedTermIds] = useState<Set<number>>(new Set());

  // Dialogs
  const [showCreateDomain, setShowCreateDomain] = useState(false);
  const [showAddTerm, setShowAddTerm] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [newDomainName, setNewDomainName] = useState("");
  const [newDomainDesc, setNewDomainDesc] = useState("");
  const [newTermSource, setNewTermSource] = useState("");
  const [newTermTarget, setNewTermTarget] = useState("");
  const [newTermLang, setNewTermLang] = useState("zh-CN");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState("");

  // Inline editing
  const [editingCell, setEditingCell] = useState<{ termId: number; field: string } | null>(null);
  const [editValue, setEditValue] = useState("");

  // All supported languages from API
  const [allLanguages, setAllLanguages] = useState<Language[]>([]);
  const [visibleLangs, setVisibleLangs] = useState<Set<string>>(new Set());
  const [showLangPicker, setShowLangPicker] = useState(false);

  const [error, setError] = useState("");

  const loadDomains = useCallback(async () => {
    try {
      const data = await fetchLibraryDomains();
      setDomains(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const loadTerms = useCallback(async () => {
    if (!selectedDomainId) return;
    try {
      const data = await fetchLibraryTerms(selectedDomainId, {
        search,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setTerms(data.terms);
      setTotalTerms(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [selectedDomainId, search, page]);

  useEffect(() => {
    loadDomains();
    fetchLanguages().then(setAllLanguages).catch(() => {});
  }, [loadDomains]);

  useEffect(() => {
    loadTerms();
  }, [loadTerms]);

  // Default visible langs = languages that have data in current terms
  useEffect(() => {
    const langsWithData = new Set(terms.flatMap((t) => Object.keys(t.targets)));
    setVisibleLangs(langsWithData);
  }, [terms]);

  const handleCreateDomain = async () => {
    if (!newDomainName.trim()) return;
    try {
      const result = await createLibraryDomain(newDomainName, newDomainDesc);
      await loadDomains();
      setSelectedDomainId(result.id);
      setShowCreateDomain(false);
      setNewDomainName("");
      setNewDomainDesc("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleDeleteDomain = async (id: number) => {
    if (!confirm("确定删除此领域及其所有术语？")) return;
    try {
      await deleteLibraryDomain(id);
      if (selectedDomainId === id) {
        setSelectedDomainId(null);
        setTerms([]);
      }
      await loadDomains();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleAddTerm = async () => {
    if (!newTermSource.trim() || !selectedDomainId) return;
    try {
      await createLibraryTerm(selectedDomainId, {
        source: newTermSource,
        targets: newTermTarget ? { [newTermLang]: newTermTarget } : {},
        strategy: "hard",
      });
      await loadTerms();
      await loadDomains();
      setShowAddTerm(false);
      setNewTermSource("");
      setNewTermTarget("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleDeleteTerm = async (termId: number) => {
    try {
      await deleteLibraryTerm(termId);
      await loadTerms();
      await loadDomains();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleBatchDelete = async () => {
    if (selectedTermIds.size === 0) return;
    if (!confirm(`确定删除选中的 ${selectedTermIds.size} 个术语？`)) return;
    try {
      await deleteLibraryTermsBatch(Array.from(selectedTermIds));
      setSelectedTermIds(new Set());
      await loadTerms();
      await loadDomains();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleImport = async () => {
    if (!importFile || !selectedDomainId) return;
    try {
      const result = await importLibraryTerms(selectedDomainId, importFile);
      setImportResult(`导入完成：新增 ${result.inserted} 个，更新 ${result.updated} 个`);
      await loadTerms();
      await loadDomains();
    } catch (err) {
      setImportResult(err instanceof Error ? err.message : String(err));
    }
  };

  const handleInlineEdit = async (termId: number, field: string) => {
    if (!editingCell) return;
    try {
      if (field === "source") {
        await updateLibraryTerm(termId, { source: editValue });
      } else if (field === "context") {
        await updateLibraryTerm(termId, { context: editValue });
      } else {
        // It's a language column
        const term = terms.find((t) => t.id === termId);
        if (term) {
          await updateLibraryTerm(termId, {
            targets: { ...term.targets, [field]: editValue },
          });
        }
      }
      setEditingCell(null);
      await loadTerms();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const toggleTermSelection = (termId: number) => {
    setSelectedTermIds((prev) => {
      const next = new Set(prev);
      if (next.has(termId)) next.delete(termId);
      else next.add(termId);
      return next;
    });
  };

  const selectedDomain = domains.find((d) => d.id === selectedDomainId);

  // Language columns: use all supported languages, filtered by visibility
  const langNameMap = Object.fromEntries(allLanguages.map((l) => [l.code, l.name]));
  const allLangs = allLanguages.length > 0
    ? allLanguages.map((l) => l.code).filter((code) => visibleLangs.has(code))
    : Array.from(visibleLangs);

  const totalPages = Math.ceil(totalTerms / PAGE_SIZE);

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {error && (
        <div className="px-14 pt-14 flex-shrink-0">
          <div className="rounded-lg px-4 py-3 text-sm bg-destructive/10 text-destructive border border-destructive/20">
            {error}
            <button className="ml-3 text-sm underline" onClick={() => setError("")}>{t('common.close')}</button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-hidden p-14">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 h-full">
            {/* Left - Domain List */}
            <div className="lg:col-span-1 flex flex-col gap-4 min-h-0">
              <div className="flex-1 overflow-auto space-y-2">
                {domains.map((d) => (
                  <Card
                    key={d.id}
                    className={`p-3 cursor-pointer transition-colors hover:bg-accent ${
                      selectedDomainId === d.id ? "border-blue-500 bg-accent" : ""
                    }`}
                    onClick={() => {
                      setSelectedDomainId(d.id);
                      setPage(0);
                      setSearch("");
                      setSelectedTermIds(new Set());
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-sm">{domainName(d)}</div>
                        {(d.description || d.description_zh) && (
                          <div className="text-xs text-muted-foreground mt-0.5">{domainDesc(d)}</div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="text-xs">
                          {d.term_count}
                        </Badge>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteDomain(d.id);
                          }}
                          className="text-muted-foreground hover:text-red-500 transition-colors"
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      </div>
                    </div>
                  </Card>
                ))}
                {domains.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-8">
                    暂无领域，点击"新建"创建
                  </p>
                )}
              </div>
            </div>

            {/* Right - Term Table */}
            <div className="lg:col-span-3 flex flex-col gap-4 min-h-0">
              {selectedDomain ? (
                <>
                  {/* Toolbar */}
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <h2 className="text-lg font-medium">{domainName(selectedDomain)}</h2>
                      <Badge>{totalTerms} 个术语</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="relative">
                        <Search className="absolute left-2 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                        <Input
                          placeholder={`${t('common.search')}...`}
                          value={search}
                          onChange={(e) => {
                            setSearch(e.target.value);
                            setPage(0);
                          }}
                          className="pl-8 h-8 w-48 text-sm"
                        />
                      </div>
                      <Button size="sm" variant="outline" onClick={() => setShowAddTerm(true)}>
                        <Plus className="size-3.5 mr-1" />
                        {t('library.addTerm')}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => { setImportFile(null); setImportResult(""); setShowImport(true); }}>
                        <Upload className="size-3.5 mr-1" />
                        {t('library.import')}
                      </Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button size="sm" variant="outline">
                            <Download className="size-3.5 mr-1" />
                            {t('library.export')}
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent>
                          <DropdownMenuItem asChild>
                            <a href={getExportUrl(selectedDomain.id, "csv")} download>CSV</a>
                          </DropdownMenuItem>
                          <DropdownMenuItem asChild>
                            <a href={getExportUrl(selectedDomain.id, "tsv")} download>TSV</a>
                          </DropdownMenuItem>
                          <DropdownMenuItem asChild>
                            <a href={getExportUrl(selectedDomain.id, "json")} download>JSON</a>
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                      <div className="relative">
                        <Button size="sm" variant="outline" onClick={() => setShowLangPicker(!showLangPicker)}>
                          <Columns className="size-3.5 mr-1" />
                          语言列
                        </Button>
                        {showLangPicker && (
                          <div className="absolute right-0 top-full mt-1 bg-card border border-border rounded-lg shadow-lg z-50 p-2 w-56 max-h-64 overflow-auto">
                            <div className="flex justify-between items-center mb-2 px-1">
                              <span className="text-xs font-medium text-muted-foreground">显示语言列</span>
                              <button className="text-xs text-foreground hover:underline" onClick={() => {
                                setVisibleLangs(new Set(allLanguages.map((l) => l.code)));
                              }}>全选</button>
                            </div>
                            {allLanguages.map((lang) => (
                              <label key={lang.code} className="flex items-center gap-2 px-1 py-1 hover:bg-accent/50 rounded cursor-pointer text-sm">
                                <input
                                  type="checkbox"
                                  checked={visibleLangs.has(lang.code)}
                                  onChange={() => {
                                    setVisibleLangs((prev) => {
                                      const next = new Set(prev);
                                      if (next.has(lang.code)) next.delete(lang.code);
                                      else next.add(lang.code);
                                      return next;
                                    });
                                  }}
                                />
                                <span>{lang.name}</span>
                                <span className="text-muted-foreground text-xs ml-auto">{lang.code}</span>
                              </label>
                            ))}
                          </div>
                        )}
                      </div>
                      {selectedTermIds.size > 0 && (
                        <Button size="sm" variant="destructive" onClick={handleBatchDelete}>
                          <Trash2 className="size-3.5 mr-1" />
                          {t('common.delete')} ({selectedTermIds.size})
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Table */}
                  <Card className="flex-1 overflow-auto">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-muted/50">
                          <TableHead className="w-8">
                            <input
                              type="checkbox"
                              checked={terms.length > 0 && selectedTermIds.size === terms.length}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedTermIds(new Set(terms.map((t) => t.id)));
                                } else {
                                  setSelectedTermIds(new Set());
                                }
                              }}
                            />
                          </TableHead>
                          <TableHead>原文</TableHead>
                          {allLangs.map((lang) => (
                            <TableHead key={lang}>{langNameMap[lang] || lang}</TableHead>
                          ))}
                          <TableHead className="w-24">策略</TableHead>
                          <TableHead>领域含义</TableHead>
                          <TableHead className="w-16 text-center">使用</TableHead>
                          <TableHead className="w-12"></TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {terms.map((term) => (
                          <TableRow key={term.id}>
                            <TableCell>
                              <input
                                type="checkbox"
                                checked={selectedTermIds.has(term.id)}
                                onChange={() => toggleTermSelection(term.id)}
                              />
                            </TableCell>
                            <TableCell>
                              {editingCell?.termId === term.id && editingCell.field === "source" ? (
                                <div className="flex items-center gap-1">
                                  <input
                                    autoFocus
                                    value={editValue}
                                    onChange={(e) => setEditValue(e.target.value)}
                                    onBlur={() => handleInlineEdit(term.id, "source")}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter") handleInlineEdit(term.id, "source");
                                      if (e.key === "Escape") setEditingCell(null);
                                    }}
                                    className="border rounded px-1.5 py-0.5 text-sm w-full"
                                  />
                                </div>
                              ) : (
                                <button
                                  className="text-sm font-medium text-left w-full hover:bg-accent/50 rounded px-1 py-0.5"
                                  onClick={() => { setEditingCell({ termId: term.id, field: "source" }); setEditValue(term.source); }}
                                >
                                  {term.source}
                                </button>
                              )}
                            </TableCell>
                            {allLangs.map((lang) => (
                              <TableCell key={lang}>
                                {editingCell?.termId === term.id && editingCell.field === lang ? (
                                  <div className="flex items-center gap-1">
                                    <input
                                      autoFocus
                                      value={editValue}
                                      onChange={(e) => setEditValue(e.target.value)}
                                      onBlur={() => handleInlineEdit(term.id, lang)}
                                      onKeyDown={(e) => {
                                        if (e.key === "Enter") handleInlineEdit(term.id, lang);
                                        if (e.key === "Escape") setEditingCell(null);
                                      }}
                                      className="border rounded px-1.5 py-0.5 text-sm w-full min-w-16"
                                    />
                                    <button onClick={() => handleInlineEdit(term.id, lang)} className="text-green-600">
                                      <CheckCircle2 className="size-4" />
                                    </button>
                                  </div>
                                ) : (
                                  <button
                                    className="text-sm text-left w-full hover:bg-accent/50 rounded px-1 py-0.5 min-h-6"
                                    onClick={() => { setEditingCell({ termId: term.id, field: lang }); setEditValue(term.targets[lang] || ""); }}
                                  >
                                    {term.targets[lang] || <span className="text-muted-foreground/40">—</span>}
                                  </button>
                                )}
                              </TableCell>
                            ))}
                            <TableCell>
                              <span className="text-xs text-muted-foreground">
                                {STRATEGY_LABELS[term.strategy] || term.strategy}
                              </span>
                            </TableCell>
                            <TableCell>
                              {editingCell?.termId === term.id && editingCell.field === "context" ? (
                                <input
                                  autoFocus
                                  value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                  onBlur={() => handleInlineEdit(term.id, "context")}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") handleInlineEdit(term.id, "context");
                                    if (e.key === "Escape") setEditingCell(null);
                                  }}
                                  className="border rounded px-1.5 py-0.5 text-xs w-full"
                                />
                              ) : (
                                <button
                                  className="text-xs text-muted-foreground text-left w-full hover:bg-accent/50 rounded px-1 py-0.5 min-h-6"
                                  onClick={() => { setEditingCell({ termId: term.id, field: "context" }); setEditValue(term.context || ""); }}
                                >
                                  {term.context || <span className="text-muted-foreground/40">—</span>}
                                </button>
                              )}
                            </TableCell>
                            <TableCell className="text-center text-xs text-muted-foreground">
                              {term.use_count}
                            </TableCell>
                            <TableCell>
                              <button
                                onClick={() => handleDeleteTerm(term.id)}
                                className="text-muted-foreground hover:text-red-500 transition-colors"
                              >
                                <Trash2 className="size-3.5" />
                              </button>
                            </TableCell>
                          </TableRow>
                        ))}
                        {terms.length === 0 && (
                          <TableRow>
                            <TableCell colSpan={allLangs.length + 6} className="text-center text-muted-foreground py-12">
                              {search ? "没有匹配的术语" : "此领域暂无术语"}
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </Card>

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <span>共 {totalTerms} 个术语，第 {page + 1}/{totalPages} 页</span>
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage(page - 1)}>
                          上一页
                        </Button>
                        <Button size="sm" variant="outline" disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>
                          下一页
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <p>请选择一个领域查看术语</p>
                </div>
              )}
            </div>
          </div>
        </div>

      {/* Create Domain Dialog */}
      <Dialog open={showCreateDomain} onOpenChange={setShowCreateDomain}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('library.addDomain')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium">名称</label>
              <Input
                value={newDomainName}
                onChange={(e) => setNewDomainName(e.target.value)}
                placeholder="例如：AI/ML、法律、医疗"
                onKeyDown={(e) => e.key === "Enter" && handleCreateDomain()}
              />
            </div>
            <div>
              <label className="text-sm font-medium">描述（可选）</label>
              <Input
                value={newDomainDesc}
                onChange={(e) => setNewDomainDesc(e.target.value)}
                placeholder="简要描述此领域"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDomain(false)}>{t('common.cancel')}</Button>
            <Button onClick={handleCreateDomain} disabled={!newDomainName.trim()}>{t('common.confirm')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Term Dialog */}
      <Dialog open={showAddTerm} onOpenChange={setShowAddTerm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('library.addTerm')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium">原文</label>
              <Input
                value={newTermSource}
                onChange={(e) => setNewTermSource(e.target.value)}
                placeholder="原文术语"
              />
            </div>
            <div>
              <label className="text-sm font-medium">目标语言</label>
              <Input
                value={newTermLang}
                onChange={(e) => setNewTermLang(e.target.value)}
                placeholder="例如 zh-CN"
              />
            </div>
            <div>
              <label className="text-sm font-medium">译文</label>
              <Input
                value={newTermTarget}
                onChange={(e) => setNewTermTarget(e.target.value)}
                placeholder="译文"
                onKeyDown={(e) => e.key === "Enter" && handleAddTerm()}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddTerm(false)}>{t('common.cancel')}</Button>
            <Button onClick={handleAddTerm} disabled={!newTermSource.trim()}>{t('common.save')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import Dialog */}
      <Dialog open={showImport} onOpenChange={setShowImport}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('library.import')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              支持 CSV/TSV 格式。首列必须为 source，其余列为语言代码（如 zh-CN, en, ja）。
            </p>
            <Input
              type="file"
              accept=".csv,.tsv,.txt"
              onChange={(e) => setImportFile(e.target.files?.[0] || null)}
            />
            {importResult && (
              <p className={`text-sm ${importResult.includes("失败") || importResult.includes("Error") ? "text-destructive" : "text-green-600"}`}>
                {importResult}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowImport(false)}>{t('common.close')}</Button>
            <Button onClick={handleImport} disabled={!importFile}>{t('library.import')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
