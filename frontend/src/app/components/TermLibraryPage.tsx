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

// Strategy labels defined inside component to access i18n

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
  const STRATEGY_LABELS: Record<string, string> = {
    hard: t('glossary.strategyEnforce'),
    keep_original: t('glossary.strategyPreserve'),
    skip: t('glossary.strategySkip'),
  };
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
  const [newTermValues, setNewTermValues] = useState<Record<string, string>>({});
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<{ message: string; type: "success" | "warning" | "error" } | null>(null);

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

  // Default visible langs = languages that have data in current terms + always include 'en'
  useEffect(() => {
    const langsWithData = new Set(terms.flatMap((t) => Object.keys(t.targets)));
    langsWithData.add("en");  // en always visible (primary lookup key)
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
    if (!confirm(t('library.confirmDeleteDomain'))) return;
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
    const enVal = (newTermValues["en"] || "").trim();
    const hasAnyValue = Object.values(newTermValues).some((v) => v.trim());
    if (!hasAnyValue || !selectedDomainId) return;
    // Use en value as source if available, otherwise first non-empty value
    const source = enVal || Object.values(newTermValues).find((v) => v.trim()) || "";
    const targets: Record<string, string> = {};
    for (const [lang, val] of Object.entries(newTermValues)) {
      if (val.trim()) targets[lang] = val.trim();
    }
    try {
      await createLibraryTerm(selectedDomainId, {
        source,
        targets,
        strategy: "hard",
      });
      await loadTerms();
      await loadDomains();
      setShowAddTerm(false);
      setNewTermValues({});
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
    if (!confirm(t('library.confirmBatchDelete').replace('{count}', String(selectedTermIds.size)))) return;
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
      let msg = t('library.importSuccess')
        .replace('{inserted}', String(result.inserted))
        .replace('{updated}', String(result.updated));
      if (result.skipped > 0) {
        msg += ' ' + t('library.importSkipped').replace('{skipped}', String(result.skipped));
      }
      if (result.warnings?.length) {
        msg += '\n' + result.warnings.join('\n');
      }
      const type = result.skipped > 0 || result.warnings?.length ? "warning" : "success";
      setImportResult({ message: msg, type });
      await loadTerms();
      await loadDomains();
    } catch (err) {
      setImportResult({ message: err instanceof Error ? err.message : String(err), type: "error" });
    }
  };

  const handleInlineEdit = async (termId: number, field: string) => {
    if (!editingCell) return;
    try {
      if (field === "context") {
        await updateLibraryTerm(termId, { context: editValue });
      } else {
        // It's a language column
        const term = terms.find((t) => t.id === termId);
        if (term) {
          const update: Record<string, unknown> = {
            targets: { ...term.targets, [field]: editValue },
          };
          // Keep DB source field in sync when editing 'en'
          if (field === "en") {
            update.source = editValue;
          }
          await updateLibraryTerm(termId, update);
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
                    {t('library.noDomains')}
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
                      <Badge>{t('library.termCount').replace('{count}', String(totalTerms))}</Badge>
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
                      <Button size="sm" variant="outline" onClick={() => { setNewTermValues({}); setShowAddTerm(true); }}>
                        <Plus className="size-3.5 mr-1" />
                        {t('library.addTerm')}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => { setImportFile(null); setImportResult(null); setShowImport(true); }}>
                        <Upload className="size-3.5 mr-1" />
                        {t('library.import')}
                      </Button>
                      <div className="flex items-center gap-0.5">
                        {(["csv", "tsv", "json"] as const).map((fmt) => (
                          <a
                            key={fmt}
                            href={getExportUrl(selectedDomain.id, fmt)}
                            download={`terms_${selectedDomain.id}.${fmt}`}
                            className="inline-flex items-center h-8 px-2 text-xs rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground transition-colors"
                          >
                            {fmt === "csv" && <Download className="size-3 mr-1" />}
                            {fmt.toUpperCase()}
                          </a>
                        ))}
                      </div>
                      <div className="relative">
                        <Button size="sm" variant="outline" onClick={() => setShowLangPicker(!showLangPicker)}>
                          <Columns className="size-3.5 mr-1" />
                          {t('library.langColumns')}
                        </Button>
                        {showLangPicker && (
                          <div className="absolute right-0 top-full mt-1 bg-card border border-border rounded-lg shadow-lg z-50 p-2 w-56 max-h-64 overflow-auto">
                            <div className="flex justify-between items-center mb-2 px-1">
                              <span className="text-xs font-medium text-muted-foreground">{t('library.showLangColumns')}</span>
                              <button className="text-xs text-foreground hover:underline" onClick={() => {
                                setVisibleLangs(new Set(allLanguages.map((l) => l.code)));
                              }}>{t('common.selectAll')}</button>
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
                          {allLangs.map((lang) => (
                            <TableHead key={lang}>{langNameMap[lang] || lang}</TableHead>
                          ))}
                          <TableHead className="w-24">{t('library.termStrategy')}</TableHead>
                          <TableHead>{t('library.termContext')}</TableHead>
                          <TableHead className="w-16 text-center">{t('library.termUsage')}</TableHead>
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
                            {allLangs.map((lang) => {
                              // For 'en' column, fall back to term.source for backward compat with existing data
                              const cellValue = term.targets[lang] || (lang === "en" ? term.source : "") || "";
                              return (
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
                                    className={`text-sm text-left w-full hover:bg-accent/50 rounded px-1 py-0.5 min-h-6 ${lang === "en" ? "font-medium" : ""}`}
                                    onClick={() => { setEditingCell({ termId: term.id, field: lang }); setEditValue(cellValue); }}
                                  >
                                    {cellValue || <span className="text-muted-foreground/40">—</span>}
                                  </button>
                                )}
                              </TableCell>
                              );
                            })}
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
                              {search ? t('library.noMatchingTerms') : t('library.noTerms')}
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </Card>

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <span>{t('library.pagination').replace('{total}', String(totalTerms)).replace('{page}', String(page + 1)).replace('{pages}', String(totalPages))}</span>
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage(page - 1)}>
                          {t('common.prevPage')}
                        </Button>
                        <Button size="sm" variant="outline" disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>
                          {t('common.nextPage')}
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <p>{t('library.selectDomain')}</p>
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
              <label className="text-sm font-medium">{t('library.domainName')}</label>
              <Input
                value={newDomainName}
                onChange={(e) => setNewDomainName(e.target.value)}
                placeholder={t('library.domainNamePlaceholder')}
                onKeyDown={(e) => e.key === "Enter" && handleCreateDomain()}
              />
            </div>
            <div>
              <label className="text-sm font-medium">{t('library.domainDescOptional')}</label>
              <Input
                value={newDomainDesc}
                onChange={(e) => setNewDomainDesc(e.target.value)}
                placeholder={t('library.domainDescPlaceholder')}
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
          <div className="space-y-2 max-h-80 overflow-auto">
            {allLanguages.length > 0 ? allLanguages.map((lang) => (
              <div key={lang.code} className="flex items-center gap-2">
                <label className="text-sm font-medium w-24 shrink-0 text-right">{lang.name}</label>
                <Input
                  value={newTermValues[lang.code] || ""}
                  onChange={(e) => setNewTermValues((prev) => ({ ...prev, [lang.code]: e.target.value }))}
                  placeholder={lang.code}
                  onKeyDown={(e) => e.key === "Enter" && handleAddTerm()}
                />
              </div>
            )) : (
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium w-24 shrink-0 text-right">en</label>
                <Input
                  value={newTermValues["en"] || ""}
                  onChange={(e) => setNewTermValues((prev) => ({ ...prev, en: e.target.value }))}
                  placeholder="en"
                  onKeyDown={(e) => e.key === "Enter" && handleAddTerm()}
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddTerm(false)}>{t('common.cancel')}</Button>
            <Button onClick={handleAddTerm} disabled={!Object.values(newTermValues).some((v) => v.trim())}>{t('common.save')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import Dialog */}
      <Dialog open={showImport} onOpenChange={setShowImport}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('library.import')}</DialogTitle>
          </DialogHeader>

          {importResult ? (
            /* ── Result state ── */
            <div className="space-y-4">
              <div className={`rounded-lg p-4 ${
                importResult.type === "error" ? "bg-destructive/10 border border-destructive/20"
                  : importResult.type === "warning" ? "bg-amber-50 border border-amber-200 dark:bg-amber-950/30 dark:border-amber-800"
                  : "bg-green-50 border border-green-200 dark:bg-green-950/30 dark:border-green-800"
              }`}>
                <div className="flex items-start gap-2">
                  {importResult.type === "error" ? (
                    <X className="size-5 text-destructive shrink-0 mt-0.5" />
                  ) : importResult.type === "warning" ? (
                    <CheckCircle2 className="size-5 text-amber-600 shrink-0 mt-0.5" />
                  ) : (
                    <CheckCircle2 className="size-5 text-green-600 shrink-0 mt-0.5" />
                  )}
                  <p className={`text-sm whitespace-pre-line ${
                    importResult.type === "error" ? "text-destructive"
                      : importResult.type === "warning" ? "text-amber-700 dark:text-amber-400"
                      : "text-green-700 dark:text-green-400"
                  }`}>
                    {importResult.message}
                  </p>
                </div>
              </div>
              <DialogFooter className="gap-2 sm:gap-0">
                <Button variant="outline" onClick={() => { setImportFile(null); setImportResult(null); }}>
                  {t('library.importAgain')}
                </Button>
                <Button onClick={() => setShowImport(false)}>{t('common.close')}</Button>
              </DialogFooter>
            </div>
          ) : (
            /* ── Upload state ── */
            <div className="space-y-4">
              {/* Format guide */}
              <div className="rounded-lg bg-muted/50 p-3 space-y-2">
                <p className="text-sm text-muted-foreground">{t('library.importStepFileDesc')}</p>
                <p className="text-xs text-muted-foreground/70 font-mono">{t('library.importFormatExample')}</p>
                <p className="text-xs text-muted-foreground/70">{t('library.importOptionalCols')}</p>
                <a href="/api/library/import-template" download
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
                  <Download className="size-3" />
                  {t('library.importTemplate')}
                </a>
              </div>

              {/* Drop zone */}
              <label className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 cursor-pointer transition-colors ${
                importFile ? "border-primary/50 bg-primary/5" : "border-muted-foreground/25 hover:border-primary/40 hover:bg-muted/30"
              }`}>
                <input
                  type="file"
                  accept=".csv,.tsv,.txt"
                  className="sr-only"
                  onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                />
                {importFile ? (
                  <>
                    <Upload className="size-5 text-primary" />
                    <span className="text-sm font-medium">{t('library.importFileSelected').replace('{name}', importFile.name)}</span>
                    <span className="text-xs text-muted-foreground">{t('library.importChangeFile')}</span>
                  </>
                ) : (
                  <>
                    <Upload className="size-5 text-muted-foreground/50" />
                    <span className="text-sm text-muted-foreground">{t('library.importDragDrop')}</span>
                    <span className="text-xs text-muted-foreground/50">CSV, TSV</span>
                  </>
                )}
              </label>

              <DialogFooter>
                <Button variant="outline" onClick={() => setShowImport(false)}>{t('common.close')}</Button>
                <Button onClick={handleImport} disabled={!importFile}>{t('library.import')}</Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
