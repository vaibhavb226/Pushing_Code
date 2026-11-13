import React, { useState, useRef } from 'react'
import { X, Upload, FileText, FileSpreadsheet, AlertCircle, CheckCircle, Loader, AlertTriangle } from 'lucide-react'
import staticBids from '../../data/bids.json'

// ── Constants ─────────────────────────────────────────────
const DOC_TYPES = [
  'Pricing', 'Spec Sheet', 'CN Label', 'PFS', 'Compliance',
  'RFP', 'Item List', 'Supplier List', 'Filing',
]
const SUP_CATEGORIES = [
  'Protein', 'Dairy', 'Bakery', 'Produce', 'Grocery',
  'Beverage', 'Paper', 'Broker',
]
const COMMON_TAGS = ['K-12', 'DoD', 'Buy American', 'Child Nutrition', 'Halal', 'Kosher', 'Whole Grain', 'PFS']

// ── Hash a File object using the browser's built-in Web Crypto API.
// Returns the hex SHA-256 string. Fast — typically < 100ms for typical doc sizes.
async function hashFile(file) {
  const buffer = await file.arrayBuffer()
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer)
  return Array.from(new Uint8Array(hashBuffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
}

// ── Field row ─────────────────────────────────────────────
function FieldRow({ label, required, children }) {
  return (
    <div className="mb-4">
      <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      {children}
    </div>
  )
}

const inputCls = 'w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-exl-orange/30 focus:border-exl-orange'

// ── Main UploadDrawer ─────────────────────────────────────
export default function UploadDrawer({ onClose, onUploaded }) {
  const fileInputRef = useRef(null)
  const [file, setFile]                     = useState(null)
  const [isDragging, setIsDragging]         = useState(false)
  const [supplier, setSupplier]             = useState('')
  const [bidId, setBidId]                   = useState('')
  const [docType, setDocType]               = useState('')
  const [supplierCategory, setSupCat]       = useState('')
  const [description, setDescription]       = useState('')
  const [tagInput, setTagInput]             = useState('')
  const [selectedTags, setSelectedTags]     = useState([])
  const [saving, setSaving]                 = useState(false)
  const [error, setError]                   = useState(null)
  const [success, setSuccess]               = useState(false)

  // Duplicate detection state
  const [checking, setChecking]             = useState(false)   // hashing + fetching in progress
  const [duplicate, setDuplicate]           = useState(null)    // existing doc record if found
  const [duplicateDismissed, setDismissed]  = useState(false)   // user chose "Upload Anyway"

  // ── Hash the file, fetch existing docs, compare hashes ──
  const checkForDuplicate = async (f) => {
    setChecking(true)
    setDuplicate(null)
    setDismissed(false)
    try {
      const [hash, res] = await Promise.all([
        hashFile(f),
        fetch('/api/documents'),
      ])
      if (!res.ok) return  // silently skip if list fetch fails — don't block upload
      const docs = await res.json()
      const existing = docs.find(d => d.fileHash === hash)
      if (existing) setDuplicate(existing)
    } catch {
      // Hash errors or network errors must never block the upload
    } finally {
      setChecking(false)
    }
  }

  // ── File drop/select handler ─────────────────────────────
  const handleFile = (f) => {
    if (!f) return
    const ext = f.name.split('.').pop().toLowerCase()
    if (!['pdf', 'xlsx', 'xls'].includes(ext)) {
      setError('Only PDF (.pdf) and Excel (.xlsx, .xls) files are accepted.')
      return
    }
    setError(null)
    setFile(f)
    if (!docType) setDocType(ext === 'pdf' ? 'Pricing' : 'Item List')
    checkForDuplicate(f)  // kick off background duplicate check immediately
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  const clearFile = (e) => {
    e?.stopPropagation()
    setFile(null)
    setDuplicate(null)
    setDismissed(false)
    setChecking(false)
  }

  const removeTag = (tag) => setSelectedTags(p => p.filter(t => t !== tag))
  const addTag    = (tag) => {
    if (tag && !selectedTags.includes(tag)) setSelectedTags(p => [...p, tag])
    setTagInput('')
  }

  // ── Save ──────────────────────────────────────────────────
  const handleSave = async () => {
    if (!file) { setError('Please select a file.'); return }
    // If a duplicate was found and the user hasn't dismissed the warning, block the save
    if (duplicate && !duplicateDismissed) { return }

    setSaving(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('supplier', supplier)
      formData.append('bidId', bidId || 'ALL')
      formData.append('documentType', docType || 'Filing')
      formData.append('supplierCategory', supplierCategory)
      formData.append('tags', selectedTags.join(','))
      formData.append('description', description)

      const res = await fetch('/api/documents/upload', { method: 'POST', body: formData })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Upload failed')

      setSuccess(true)
      setTimeout(() => {
        onUploaded(data.document)
        onClose()
      }, 800)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  // ── Drop zone border changes based on state ──────────────
  const zoneBorder = isDragging
    ? 'border-exl-orange bg-exl-orange/5'
    : duplicate && !duplicateDismissed
      ? 'border-amber-400 bg-amber-50'
      : file
        ? 'border-emerald-400 bg-emerald-50'
        : 'border-gray-200 hover:border-exl-orange/50 hover:bg-gray-50'

  // ── Render ───────────────────────────────────────────────
  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Drawer panel */}
      <div className="fixed right-0 top-0 bottom-0 w-[440px] bg-white shadow-2xl z-50 flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-exl-navy flex-shrink-0">
          <div>
            <h2 className="text-white font-bold text-base">Upload Document</h2>
            <p className="text-blue-300 text-xs mt-0.5">Add to the Document Vault</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5">

          {/* Success state */}
          {success && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mb-4">
                <CheckCircle className="w-8 h-8 text-emerald-600" />
              </div>
              <p className="text-lg font-bold text-gray-900">Uploaded!</p>
              <p className="text-sm text-gray-500 mt-1">Document added to vault</p>
            </div>
          )}

          {!success && (
            <>
              {/* File drop zone */}
              <FieldRow label="File" required>
                <div
                  onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={handleDrop}
                  onClick={() => !file && fileInputRef.current?.click()}
                  className={`
                    border-2 border-dashed rounded-xl p-6 text-center transition-all
                    ${file ? 'cursor-default' : 'cursor-pointer'}
                    ${zoneBorder}
                  `}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.xlsx,.xls"
                    className="hidden"
                    onChange={(e) => handleFile(e.target.files[0])}
                  />

                  {/* Checking state — shown briefly while hashing */}
                  {checking && (
                    <div className="flex items-center justify-center gap-2 text-gray-500">
                      <Loader className="w-5 h-5 animate-spin" />
                      <span className="text-sm">Checking for duplicates…</span>
                    </div>
                  )}

                  {/* File selected, no duplicate (or dismissed) */}
                  {!checking && file && (
                    <div className="flex items-center justify-center gap-3">
                      {file.name.endsWith('.pdf')
                        ? <FileText className="w-8 h-8 text-red-500 flex-shrink-0" />
                        : <FileSpreadsheet className="w-8 h-8 text-emerald-600 flex-shrink-0" />
                      }
                      <div className="text-left min-w-0">
                        <p className="text-sm font-semibold text-gray-900 truncate">{file.name}</p>
                        <p className="text-xs text-gray-500">{Math.max(1, Math.round(file.size / 1024))} KB</p>
                      </div>
                      <button
                        onClick={clearFile}
                        className="ml-2 text-gray-400 hover:text-red-500 flex-shrink-0"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  )}

                  {/* Empty state */}
                  {!checking && !file && (
                    <>
                      <Upload className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                      <p className="text-sm font-medium text-gray-600">Drop file here or click to browse</p>
                      <p className="text-xs text-gray-400 mt-1">PDF or Excel · Max 20 MB</p>
                    </>
                  )}
                </div>

                {/* ── Duplicate warning — shown immediately after file select ── */}
                {duplicate && !duplicateDismissed && (
                  <div className="mt-3 border border-amber-300 bg-amber-50 rounded-xl p-4">
                    <div className="flex items-start gap-3">
                      <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-amber-900">
                          This file has already been uploaded
                        </p>
                        <div className="mt-1.5 space-y-0.5">
                          <p className="text-xs text-amber-800">
                            <span className="font-medium">File:</span> {duplicate.fileName}
                          </p>
                          <p className="text-xs text-amber-800">
                            <span className="font-medium">Uploaded:</span> {duplicate.uploadDate}
                          </p>
                          {duplicate.supplier && (
                            <p className="text-xs text-amber-800">
                              <span className="font-medium">Supplier:</span> {duplicate.supplier}
                            </p>
                          )}
                          <p className="text-xs text-amber-800">
                            <span className="font-medium">Type:</span> {duplicate.documentType}
                          </p>
                          <p className="text-xs text-amber-700 font-mono mt-1">
                            ID: {duplicate.id}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="flex gap-2 mt-3">
                      <button
                        type="button"
                        onClick={clearFile}
                        className="flex-1 px-3 py-2 text-xs font-semibold bg-white border border-amber-300 text-amber-800 rounded-lg hover:bg-amber-100 transition-colors"
                      >
                        Choose Different File
                      </button>
                      <button
                        type="button"
                        onClick={() => setDismissed(true)}
                        className="flex-1 px-3 py-2 text-xs font-semibold bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors"
                      >
                        Upload Anyway
                      </button>
                    </div>
                  </div>
                )}

                {/* Dismissed notice — user chose to upload anyway */}
                {duplicate && duplicateDismissed && (
                  <div className="mt-2 flex items-center gap-2 text-xs text-gray-500 px-1">
                    <AlertCircle className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
                    Uploading as a new copy of a previously uploaded file
                  </div>
                )}
              </FieldRow>

              {/* Supplier name */}
              <FieldRow label="Supplier Name">
                <input
                  type="text"
                  value={supplier}
                  onChange={e => setSupplier(e.target.value)}
                  placeholder="e.g. Tyson Foods Inc."
                  className={inputCls}
                />
              </FieldRow>

              {/* Bid ID */}
              <FieldRow label="Bid ID">
                <select value={bidId} onChange={e => setBidId(e.target.value)} className={inputCls}>
                  <option value="">ALL Bids</option>
                  {staticBids.map(b => (
                    <option key={b.id} value={b.id}>{b.id} — {b.customer}</option>
                  ))}
                </select>
              </FieldRow>

              {/* Document type */}
              <FieldRow label="Document Type" required>
                <select value={docType} onChange={e => setDocType(e.target.value)} className={inputCls}>
                  <option value="">Select type…</option>
                  {DOC_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </FieldRow>

              {/* Supplier category */}
              <FieldRow label="Supplier Category">
                <select value={supplierCategory} onChange={e => setSupCat(e.target.value)} className={inputCls}>
                  <option value="">None (group by document type)</option>
                  {SUP_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </FieldRow>

              {/* Tags */}
              <FieldRow label="Tags">
                <div className="flex flex-wrap gap-1 mb-2">
                  {COMMON_TAGS.map(t => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => selectedTags.includes(t) ? removeTag(t) : addTag(t)}
                      className={`px-2 py-0.5 text-xs rounded-full border transition-all ${
                        selectedTags.includes(t)
                          ? 'bg-exl-orange text-white border-exl-orange'
                          : 'bg-white text-gray-600 border-gray-200 hover:border-exl-orange/50'
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={tagInput}
                    onChange={e => setTagInput(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(tagInput.trim()) } }}
                    placeholder="Type custom tag, press Enter"
                    className={`${inputCls} flex-1`}
                  />
                </div>
                {selectedTags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {selectedTags.map(t => (
                      <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 bg-exl-navy/10 text-exl-navy text-xs font-medium rounded-full">
                        {t}
                        <button onClick={() => removeTag(t)} className="hover:text-red-500">
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </FieldRow>

              {/* Description */}
              <FieldRow label="Description (optional)">
                <textarea
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  placeholder="Brief description of this document…"
                  rows={2}
                  className={`${inputCls} resize-none`}
                />
              </FieldRow>

              {/* Error */}
              {error && (
                <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  {error}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {!success && (
          <div className="border-t border-gray-200 px-6 py-4 flex gap-3 flex-shrink-0">
            <button onClick={onClose} className="btn-secondary flex-1">Cancel</button>
            <button
              onClick={handleSave}
              disabled={saving || !file || checking || (duplicate && !duplicateDismissed)}
              className="btn-primary flex-1 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving
                ? <><Loader className="w-4 h-4 animate-spin" /> Uploading…</>
                : checking
                  ? <><Loader className="w-4 h-4 animate-spin" /> Checking…</>
                  : <><Upload className="w-4 h-4" /> Save to Vault</>
              }
            </button>
          </div>
        )}
      </div>
    </>
  )
}
