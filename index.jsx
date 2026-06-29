import React, { useState, useRef, useEffect } from 'react'
import { useNavigate, useBlocker } from 'react-router-dom'
import {
  Upload, FileText, FileSpreadsheet, X, Brain, CheckCircle,
  AlertCircle, Loader, ChevronRight, Info, Calendar, AlertTriangle,
} from 'lucide-react'

// ── Constants ─────────────────────────────────────────────
const STAGES = [
  { key: 'uploading',   label: 'Uploading',   msg: '📄 Reading RFP document...' },
  { key: 'extracting', label: 'Extracting',  msg: '📄 Reading RFP document...' },
  { key: 'parsing',    label: 'AI Parsing',  msg: '🤖 AI extracting bid details...' },
  { key: 'mapping',    label: 'Mapping',     msg: '📋 Building working file...' },
  { key: 'complete',   label: 'Done',        msg: '' },
]

const SEGMENTS  = ['K-12', 'DoD', 'University', 'Healthcare', 'Restaurant', 'Lodging', 'Government']
const REGIONS   = ['Northeast', 'Southeast', 'Midwest', 'Mountain', 'Southwest', 'Northwest', 'National']
const COMP_FLAGS = ['Buy American', 'Child Nutrition', 'PFS', 'SOX', 'Halal', 'Kosher', 'Whole Grain', 'Exact Spec']

const today = () => new Date().toISOString().split('T')[0]

const subtractDays = (dateStr, n) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  d.setDate(d.getDate() - n)
  return d.toISOString().split('T')[0]
}

const fmtDate = (d) => d
  ? new Date(d + 'T12:00:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
  : ''

// ── Compliance pill (read-only, for BEX parse results display) ──
const COMP_PILLS = [
  { key: 'buy_american',    label: 'Buy Am.', cls: 'bg-red-100 text-red-700' },
  { key: 'child_nutrition', label: 'CN',      cls: 'bg-blue-100 text-blue-700' },
  { key: 'pfs_required',    label: 'PFS',     cls: 'bg-purple-100 text-purple-700' },
  { key: 'exact_spec',      label: 'ES',      cls: 'bg-amber-100 text-amber-700' },
]
function CompliancePills({ item }) {
  return (
    <div className="flex flex-wrap gap-1">
      {COMP_PILLS.map(p => item[p.key] ? (
        <span key={p.key} className={`inline-flex px-1.5 py-0.5 rounded text-xs font-semibold ${p.cls}`}>{p.label}</span>
      ) : null)}
    </div>
  )
}

// ── File drop zone ────────────────────────────────────────
function FileZone({ accept, file, onFile, onRemove, icon: Icon, iconColor, label, sublabel, required }) {
  const ref = useRef(null)
  const [dragging, setDragging] = useState(false)

  const handleDrop = (e) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]; if (f) onFile(f)
  }

  const baseStyle = {
    height: 160,
    borderRadius: 16,
    transition: 'all 0.2s ease',
    position: 'relative',
    cursor: file ? 'default' : 'pointer',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  }

  const stateStyle = file
    ? { border: '1.5px solid #16A34A', backgroundColor: '#F0FFF4' }
    : dragging
    ? { border: '1.5px dashed #E05A2B', backgroundColor: '#FFF7F5' }
    : { border: '1.5px dashed #D1D5DB', backgroundColor: 'white', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }

  const hoverHandlers = file ? {} : {
    onMouseEnter: e => { if (!dragging) { e.currentTarget.style.borderColor = '#E05A2B'; e.currentTarget.style.backgroundColor = '#FFF7F5' } },
    onMouseLeave: e => { if (!dragging) { e.currentTarget.style.borderColor = '#D1D5DB'; e.currentTarget.style.backgroundColor = 'white' } },
  }

  return (
    <div>
      <div
        style={{ ...baseStyle, ...stateStyle }}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !file && ref.current?.click()}
        {...hoverHandlers}
      >
        <input ref={ref} type="file" accept={accept} className="hidden"
          onChange={(e) => e.target.files[0] && onFile(e.target.files[0])} />

        {file ? (
          /* ── Filled state ── */
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', width: '100%', padding: '0 16px', gap: 6 }}>
            {/* Remove button — absolute, does not affect flow */}
            <button
              onClick={(e) => { e.stopPropagation(); onRemove() }}
              style={{
                position: 'absolute', top: 10, right: 10,
                width: 22, height: 22, borderRadius: '50%',
                backgroundColor: '#F3F4F6', border: 'none', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
              title="Remove file"
            >
              <X style={{ width: 12, height: 12, color: '#6B7280' }} />
            </button>
            {/* Checkmark + icon — centered row */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
              <CheckCircle style={{ width: 16, height: 16, color: '#16A34A', flexShrink: 0 }} />
              <Icon style={{ width: 20, height: 20, color: iconColor, flexShrink: 0 }} />
            </div>
            {/* Filename — centered, truncated */}
            <p style={{ fontSize: 12, fontWeight: 700, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '90%', margin: 0 }}>
              {file.name}
            </p>
            {/* Size + status — centered */}
            <p style={{ fontSize: 11, color: '#6B7280', margin: 0 }}>
              {Math.max(1, Math.round(file.size / 1024))} KB
              <span style={{ color: '#16A34A', fontWeight: 600, marginLeft: 6 }}>· Ready</span>
            </p>
          </div>
        ) : (
          /* ── Empty state ── */
          <div style={{ textAlign: 'center', padding: '0 16px' }}>
            <Icon style={{ width: 36, height: 36, color: iconColor, margin: '0 auto 10px auto', display: 'block' }} />
            <p style={{ fontSize: 13, fontWeight: 600, color: '#374151', margin: '0 0 2px 0' }}>{label}</p>
            <p style={{ fontSize: 11, color: '#9CA3AF', margin: '0 0 8px 0' }}>{sublabel}</p>
            <p style={{ fontSize: 11, color: '#E05A2B', margin: 0 }}>+ Click to upload or drag &amp; drop</p>
          </div>
        )}
      </div>

      {/* Required / Optional badge below box */}
      <div style={{ textAlign: 'center', marginTop: 6 }}>
        {required ? (
          <span style={{ fontSize: 10, fontWeight: 600, color: '#DC2626', backgroundColor: '#FEE2E2', padding: '2px 8px', borderRadius: 99 }}>Required</span>
        ) : (
          <span style={{ fontSize: 10, fontWeight: 600, color: '#6B7280', backgroundColor: '#F3F4F6', padding: '2px 8px', borderRadius: 99 }}>Optional</span>
        )}
      </div>
    </div>
  )
}

// ── Progress indicator ────────────────────────────────────
function ProgressBar({ stage }) {
  const idx = STAGES.findIndex(s => s.key === stage)
  return (
    <div className="py-8">
      <div className="flex items-center justify-between mb-3">
        {STAGES.map((s, i) => (
          <React.Fragment key={s.key}>
            <div className="flex flex-col items-center gap-1.5">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all
                ${i < idx ? 'bg-emerald-500 text-white'
                : i === idx ? 'bg-exl-orange text-white ring-4 ring-exl-orange/20'
                : 'bg-gray-200 text-gray-400'}`}>
                {i < idx ? <CheckCircle className="w-4 h-4" /> : i + 1}
              </div>
              <span className={`text-xs font-medium whitespace-nowrap
                ${i === idx ? 'text-exl-orange' : i < idx ? 'text-emerald-600' : 'text-gray-400'}`}>
                {s.label}
              </span>
            </div>
            {i < STAGES.length - 1 && (
              <div className={`flex-1 h-0.5 mx-2 mb-5 transition-all ${i < idx ? 'bg-emerald-400' : 'bg-gray-200'}`} />
            )}
          </React.Fragment>
        ))}
      </div>
      {stage !== 'complete' && (
        <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
          <Loader className="w-4 h-4 animate-spin text-exl-orange" />
          <span>{STAGES.find(s => s.key === stage)?.msg || STAGES.find(s => s.key === stage)?.label}</span>
        </div>
      )}
    </div>
  )
}

// ── Line Items tab ────────────────────────────────────────
function LineItemsTab({ items }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm min-w-[900px]">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 w-12">#</th>
            <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 w-24">MPC Code</th>
            <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 min-w-[200px]">Description</th>
            <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500">Category</th>
            <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500">UOM</th>
            <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-500">Volume</th>
            <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 min-w-[180px]">Compliance</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr key={i} className="border-b border-gray-50 hover:bg-gray-50/80 transition-colors">
              <td className="px-3 py-2.5"><span className="font-mono text-xs text-gray-400">{item.line_number || i + 1}</span></td>
              <td className="px-3 py-2.5"><span className="font-mono text-xs text-gray-600">{item.mpc_code || '—'}</span></td>
              <td className="px-3 py-2.5">
                <p className="text-sm text-gray-900 font-medium">{item.description}</p>
                {item.coding_notes && <p className="text-xs text-gray-400 mt-0.5 italic">{item.coding_notes}</p>}
              </td>
              <td className="px-3 py-2.5">
                <span className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded-full font-medium">{item.category || '—'}</span>
              </td>
              <td className="px-3 py-2.5"><span className="text-xs text-gray-600">{item.uom || '—'}</span></td>
              <td className="px-3 py-2.5 text-right">
                <span className="text-sm font-semibold text-exl-navy">{(item.volume ?? item.est_qty) ? (item.volume ?? item.est_qty).toLocaleString() : '—'}</span>
              </td>
              <td className="px-3 py-2.5"><CompliancePills item={item} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Supplier Targeting section ────────────────────────────
function SupplierTargeting({ targeting }) {
  if (!targeting) return null
  return (
    <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
      {[
        { label: 'Categories Needed',            items: targeting.categories_needed,             dot: 'bg-blue-400' },
        { label: 'Compliance Requirements',       items: targeting.compliance_requirements,       dot: 'bg-red-400' },
        { label: 'Recommended Outreach Segments', items: targeting.recommended_outreach_segments, dot: 'bg-emerald-400' },
      ].map(({ label, items, dot }) => (
        <div key={label} className="bg-white border border-gray-100 rounded-xl p-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">{label}</p>
          <ul className="space-y-1.5">
            {(items || []).map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-gray-700">
                <span className={`w-1.5 h-1.5 rounded-full ${dot} flex-shrink-0 mt-1`} />
                {item}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

// ── Form field wrapper ────────────────────────────────────
function FormField({ label, required, hint, error, children }) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
        {hint && <span className="text-gray-400 font-normal ml-2 normal-case">{hint}</span>}
      </label>
      {children}
      {error && (
        <p className="mt-1 text-xs text-red-600 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" /> {error}
        </p>
      )}
    </div>
  )
}

const inputCls = (err) =>
  `w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 transition-colors
   ${err
     ? 'border-red-400 bg-red-50 focus:ring-red-200 focus:border-red-500'
     : 'border-gray-200 bg-white focus:ring-exl-orange/30 focus:border-exl-orange'
   }`

// ── Step 2 — Bid Details Form ─────────────────────────────
function BidDetailsForm({ result, onSaved, onReset }) {
  const detectedCategories = [...new Set((result.line_items || []).map(li => li.category).filter(Boolean))]

  const [form, setForm] = useState({
    customerName:    result.metadata?.customer_name     || '',
    bidId:           result.metadata?.bid_id            || '',
    segment:         result.metadata?.segment           || 'K-12',
    opcoCode:        result.metadata?.opco_code         || '',
    opcoName:        result.metadata?.opco_name         || '',
    region:          result.metadata?.region            || '',
    bidRelease:      today(),
    customerDue:     result.metadata?.customer_due_date || '',
    internalDue:     subtractDays(result.metadata?.customer_due_date, 5),
    complianceFlags: Array.isArray(result.metadata?.compliance_flags) ? result.metadata.compliance_flags : [],
    notes:           '',
  })
  const [errors,    setErrors]    = useState({})
  const [saving,    setSaving]    = useState(false)
  const [saveError, setSaveError] = useState(null)

  const update = (key, val) => {
    setForm(prev => {
      const next = { ...prev, [key]: val }
      if (key === 'customerDue') next.internalDue = subtractDays(val, 5)
      return next
    })
    if (errors[key]) setErrors(prev => { const e = { ...prev }; delete e[key]; return e })
  }

  const toggleFlag = (flag) => {
    setForm(prev => ({
      ...prev,
      complianceFlags: prev.complianceFlags.includes(flag)
        ? prev.complianceFlags.filter(f => f !== flag)
        : [...prev.complianceFlags, flag],
    }))
  }

  const autoGenerateBidId = () => {
    const code = form.customerName
      .split(/\s+/).filter(w => w.length > 2).map(w => w[0]).join('').toUpperCase().slice(0, 3)
    return `BID-${code || 'NEW'}-${new Date().getFullYear()}`
  }

  const validate = () => {
    const errs = {}
    if (!form.customerName.trim()) errs.customerName = 'This field is required'
    if (!form.segment)             errs.segment      = 'This field is required'
    if (!form.customerDue)         errs.customerDue  = 'This field is required'
    return errs
  }

  const handleSave = async () => {
    const errs = validate()
    if (Object.keys(errs).length > 0) { setErrors(errs); return }

    setSaving(true)
    setSaveError(null)
    const bidId = form.bidId.trim() || autoGenerateBidId()

    try {
      const res = await fetch('/api/bids', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id:                 bidId,
          customer:           form.customerName.trim(),
          opco:               form.opcoCode   || '000',
          opcoName:           form.opcoName   || 'Sysco OpCo',
          region:             form.region     || 'Unknown',
          segment:            form.segment,
          status:             'Active',
          intakeDate:         today(),
          bidRelease:         form.bidRelease || today(),
          customerDue:        form.customerDue,
          internalDue:        form.internalDue || subtractDays(form.customerDue, 5),
          notes:              form.notes,
          items:              (result.line_items || []).length,
          suppliersContacted: 0,
          responsesReceived:  0,
          compliance:         form.complianceFlags,
          itemCategories:     detectedCategories,
          lineItems:          result.line_items || [],
          // Temp file paths from BEX parse step — backend will rename & store
          tempPdfPath:        result.tempPdfPath        || null,
          tempExcelPath:      result.tempExcelPath       || null,
          pdfOriginalName:    result.pdfOriginalName     || null,
          excelOriginalName:  result.excelOriginalName   || null,
          pdfSize:            result.pdfSize             || null,
          excelSize:          result.excelSize           || null,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed to save bid')
      onSaved(data.bidId, data.lineItemsCreated ?? 0)
    } catch (err) {
      setSaveError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card mb-6 overflow-hidden">

      {/* ── Header ── */}
      <div className="px-6 py-4 border-b border-gray-200 bg-emerald-50/60">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 bg-emerald-500 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            2
          </div>
          <div>
            <p className="text-sm font-bold text-gray-900">Confirm Bid Details</p>
            <p className="text-xs text-gray-500 mt-0.5">Review and complete the fields below before saving — pre-filled from BEX AI where available</p>
          </div>
          <div className="ml-auto flex items-center gap-1.5 bg-emerald-100 text-emerald-700 text-xs font-semibold px-2.5 py-1 rounded-full">
            <CheckCircle className="w-3.5 h-3.5" />
            {result.line_items?.length ?? 0} items parsed
          </div>
        </div>
      </div>

      <div className="px-6 py-5 space-y-5">

        {/* ── Row 1: Customer Name + Bid ID ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField label="Customer Name" required error={errors.customerName}>
            <input
              type="text"
              value={form.customerName}
              onChange={e => update('customerName', e.target.value)}
              placeholder="e.g. Arapahoe Charter School District"
              className={inputCls(errors.customerName)}
            />
          </FormField>
          <FormField label="Bid ID / RFP Number" hint="Auto-generated if left blank">
            <input
              type="text"
              value={form.bidId}
              onChange={e => update('bidId', e.target.value)}
              placeholder="e.g. BID-LKV-2026"
              className={inputCls(null)}
            />
          </FormField>
        </div>

        {/* ── Row 2: Segment + OpCo Code + OpCo Name ── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <FormField label="Segment" required error={errors.segment}>
            <select
              value={form.segment}
              onChange={e => update('segment', e.target.value)}
              className={inputCls(errors.segment)}
            >
              <option value="">— Select —</option>
              {SEGMENTS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </FormField>
          <FormField label="OpCo Code">
            <input
              type="text"
              value={form.opcoCode}
              onChange={e => update('opcoCode', e.target.value)}
              placeholder="e.g. 028"
              className={inputCls(null)}
            />
          </FormField>
          <FormField label="OpCo Name">
            <input
              type="text"
              value={form.opcoName}
              onChange={e => update('opcoName', e.target.value)}
              placeholder="e.g. Sysco Chicago"
              className={inputCls(null)}
            />
          </FormField>
        </div>

        {/* ── Row 3: Region + Dates ── */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <FormField label="Region">
            <select
              value={form.region}
              onChange={e => update('region', e.target.value)}
              className={inputCls(null)}
            >
              <option value="">— Select —</option>
              {REGIONS.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </FormField>
          <FormField label="Bid Release Date">
            <input
              type="date"
              value={form.bidRelease}
              onChange={e => update('bidRelease', e.target.value)}
              className={inputCls(null)}
            />
          </FormField>
          <FormField label="Customer Due Date" required error={errors.customerDue}>
            <input
              type="date"
              value={form.customerDue}
              onChange={e => update('customerDue', e.target.value)}
              className={inputCls(errors.customerDue)}
            />
          </FormField>
          <FormField label="Internal Due Date" hint="Auto: 5 days before customer due">
            <input
              type="date"
              value={form.internalDue}
              onChange={e => update('internalDue', e.target.value)}
              className={inputCls(null)}
            />
          </FormField>
        </div>

        {/* ── Row 4: Compliance Flags + Item Categories ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

          {/* Compliance checkboxes */}
          <div>
            <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2.5">Compliance Flags</p>
            <div className="flex flex-wrap gap-2">
              {COMP_FLAGS.map(flag => {
                const checked = form.complianceFlags.includes(flag)
                return (
                  <label
                    key={flag}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold cursor-pointer border transition-all select-none
                      ${checked
                        ? 'bg-exl-navy text-white border-exl-navy shadow-sm'
                        : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'
                      }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleFlag(flag)}
                      className="sr-only"
                    />
                    {checked && <CheckCircle className="w-3 h-3" />}
                    {flag}
                  </label>
                )
              })}
            </div>
          </div>

          {/* Item categories (read-only) */}
          <div>
            <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">Item Categories</p>
            <p className="text-xs text-gray-400 mb-2.5">Detected from item list</p>
            {detectedCategories.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {detectedCategories.map(cat => (
                  <span key={cat} className="px-2.5 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded-full text-xs font-semibold">
                    {cat}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 italic">No categories detected</p>
            )}
          </div>
        </div>

        {/* ── Row 5: Notes ── */}
        <FormField label="Notes (Optional)">
          <textarea
            rows={3}
            value={form.notes}
            onChange={e => update('notes', e.target.value)}
            placeholder="Any internal notes for the Bid COE team…"
            className={`${inputCls(null)} resize-none`}
          />
        </FormField>

        {/* ── Summary line ── */}
        <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-2.5 text-sm text-gray-600 flex flex-wrap gap-x-3 gap-y-1 items-center">
          <span>
            <span className="font-semibold text-exl-navy">{result.line_items?.length ?? 0} line items</span>
            {' '}extracted
          </span>
          <span className="text-gray-300">·</span>
          <span>
            Segment: <span className="font-semibold text-gray-800">{form.segment || '—'}</span>
          </span>
          {form.customerDue && (
            <>
              <span className="text-gray-300">·</span>
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-gray-400" />
                Due: <span className="font-semibold text-gray-800">{fmtDate(form.customerDue)}</span>
              </span>
            </>
          )}
          {form.complianceFlags.length > 0 && (
            <>
              <span className="text-gray-300">·</span>
              <span>Flags: <span className="font-semibold text-gray-800">{form.complianceFlags.join(', ')}</span></span>
            </>
          )}
        </div>

        {/* ── Save error ── */}
        {saveError && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" /> {saveError}
          </div>
        )}

        {/* ── Actions ── */}
        <div className="flex items-center justify-between pt-1">
          <button onClick={onReset} className="btn-secondary text-sm">
            ← Parse Another RFP
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-xl transition-colors shadow-sm"
          >
            {saving
              ? <><Loader className="w-4 h-4 animate-spin" /> Saving…</>
              : <><CheckCircle className="w-4 h-4" /> Save Bid &amp; Open Working File <ChevronRight className="w-4 h-4" /></>
            }
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Toast ─────────────────────────────────────────────────
function Toast({ message, onDone }) {
  useEffect(() => {
    const t = setTimeout(onDone, 2500)
    return () => clearTimeout(t)
  }, [])
  return (
    <div className="fixed bottom-6 right-6 z-50 bg-emerald-700 text-white text-sm font-semibold px-5 py-3 rounded-xl shadow-xl flex items-center gap-2.5">
      <CheckCircle className="w-4 h-4 flex-shrink-0" /> {message}
    </div>
  )
}

// ── Main UploadRFP page ───────────────────────────────────
export default function UploadRFP() {
  const navigate = useNavigate()

  const [pdfFile,   setPdfFile]   = useState(null)
  const [excelFile, setExcelFile] = useState(null)
  const [stage,     setStage]     = useState(null)
  const [result,    setResult]    = useState(null)
  const [error,     setError]     = useState(null)
  const [activeTab, setActiveTab] = useState('items')
  const [demoMode,  setDemoMode]  = useState(false)
  const [toast,     setToast]     = useState(null)   // { message }
  // Tracks whether files have been uploaded but bid not yet saved
  const [bidSaved,  setBidSaved]  = useState(false)

  const canParse = pdfFile || excelFile
  const hasUnsavedFiles = (pdfFile !== null || excelFile !== null) && !bidSaved

  // ── Browser tab close / refresh warning ──────────────
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (hasUnsavedFiles) {
        e.preventDefault()
        e.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [hasUnsavedFiles])

  // ── In-app navigation blocker (intercepts sidebar + back button) ──
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      hasUnsavedFiles &&
      currentLocation.pathname !== nextLocation.pathname
  )

  // ── Stage animation ───────────────────────────────────
  const simulateStages = async () => {
    // Delays match the progressive messages: 800ms reading, 2000ms AI, 1200ms mapping
    const steps = [
      { key: 'uploading',  delay: 800  },
      { key: 'extracting', delay: 1200 },
      { key: 'parsing',    delay: 2000 },
      { key: 'mapping',    delay: 800  },
    ]
    for (const { key, delay } of steps) {
      setStage(key)
      await new Promise(r => setTimeout(r, delay))
    }
  }

  // ── Parse RFP ─────────────────────────────────────────
  const handleParse = async () => {
    setError(null); setResult(null)
    const progressPromise = simulateStages()
    try {
      const formData = new FormData()
      if (pdfFile)   formData.append('pdf',   pdfFile)
      if (excelFile) formData.append('excel', excelFile)
      const res = await fetch('/api/parse-rfp', { method: 'POST', body: formData })
      let data
      try {
        data = await res.json()
      } catch {
        throw new Error(
          res.status >= 500
            ? 'Server error — check that ANTHROPIC_API_KEY is set in backend_py/.env and restart the backend'
            : `Request failed (HTTP ${res.status}) — make sure the backend is running on port 3001`
        )
      }
      if (!res.ok) {
        const msg = [data.error, data.hint].filter(Boolean).join(' — ')
        throw new Error(msg || 'Parse failed')
      }
      await progressPromise
      setStage('complete')
      setResult(data)
      setDemoMode(!!(data.parsing_warnings?.some(w => w.toLowerCase().includes('demo'))))
    } catch (err) {
      await progressPromise
      setStage(null)
      setError(err.message)
    }
  }

  // ── After bid saved ───────────────────────────────────
  const handleSaved = (bidId, itemCount) => {
    setBidSaved(true)   // clear unsaved guard before navigating
    setToast({ message: `Bid ${bidId} created — ${itemCount} items imported` })
    setTimeout(() => navigate(`/bids/${bidId}?tab=workingfile`), 1400)
  }

  const handleReset = () => {
    setResult(null); setStage(null); setPdfFile(null); setExcelFile(null)
    setError(null); setActiveTab('items')
  }

  // ── Render ────────────────────────────────────────────
  return (
    <div className="max-w-screen-xl mx-auto">

      {/* ── Page header ── */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-exl-navy flex items-center gap-2.5">
            <span className="w-8 h-8 bg-exl-orange/10 rounded-xl flex items-center justify-center">
              <Brain className="w-4 h-4 text-exl-orange" />
            </span>
            Upload RFP
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            BEX AI — parse any RFP document and extract all line items with compliance flags
          </p>
        </div>
      </div>

      {/* ── Step 1: Upload card ── */}
      <div className="mb-6" style={{ backgroundColor: 'white', borderRadius: 20, boxShadow: '0 2px 12px rgba(0,0,0,0.08)', padding: 32 }}>
        {/* Card header */}
        <div className="flex items-center gap-3 mb-2">
          <div style={{
            width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
            backgroundColor: result ? '#10B981' : '#E05A2B',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'white', fontSize: 12, fontWeight: 700,
          }}>
            {result ? <CheckCircle style={{ width: 14, height: 14 }} /> : '1'}
          </div>
          <div>
            <p style={{ fontSize: 15, fontWeight: 700, color: '#1F3864', margin: 0 }}>Upload RFP Documents</p>
            <p style={{ fontSize: 12, color: '#9CA3AF', margin: 0, marginTop: 2 }}>
              Drag &amp; drop or click to select files. BEX AI will parse automatically.
            </p>
          </div>
          {result && <span style={{ marginLeft: 'auto', fontSize: 12, color: '#059669', fontWeight: 600 }}>✓ Parsed</span>}
        </div>

        {/* Drop zones */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-5 mb-6">
          <FileZone
            accept=".pdf"
            file={pdfFile}
            onFile={setPdfFile}
            onRemove={() => setPdfFile(null)}
            icon={FileText}
            iconColor="#EF4444"
            label="RFP Document"
            sublabel="PDF format"
            required
          />
          <FileZone
            accept=".xlsx,.xls"
            file={excelFile}
            onFile={setExcelFile}
            onRemove={() => setExcelFile(null)}
            icon={FileSpreadsheet}
            iconColor="#16A34A"
            label="Item List"
            sublabel="Excel format"
            required={false}
          />
        </div>

        {/* Parse button */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
          <button
            onClick={handleParse}
            disabled={!canParse || (stage && stage !== 'complete')}
            style={{
              height: 48,
              maxWidth: 400,
              width: '100%',
              borderRadius: 12,
              border: 'none',
              cursor: (!canParse || (stage && stage !== 'complete')) ? 'not-allowed' : 'pointer',
              backgroundColor: (!canParse || (stage && stage !== 'complete')) ? '#D1D5DB' : '#E05A2B',
              color: 'white',
              fontSize: 14,
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              transition: 'background-color 0.15s ease',
              opacity: (!canParse && !stage) ? 0.6 : 1,
            }}
            onMouseEnter={e => { if (canParse && !(stage && stage !== 'complete')) e.currentTarget.style.backgroundColor = '#C94E22' }}
            onMouseLeave={e => { if (canParse && !(stage && stage !== 'complete')) e.currentTarget.style.backgroundColor = '#E05A2B' }}
          >
            {stage && stage !== 'complete'
              ? <><Loader style={{ width: 18, height: 18 }} className="animate-spin" /> Parsing RFP…</>
              : <><span style={{ fontSize: 16 }}>⚡</span> {result ? 'Re-parse RFP with BEX AI' : 'Parse RFP with BEX AI'}</>
            }
          </button>
          {!canParse && !stage && (
            <p style={{ fontSize: 11, color: '#9CA3AF', margin: 0 }}>
              No files? Click Parse RFP anyway to run with demo data
            </p>
          )}
        </div>
      </div>

      {/* ── Progress ── */}
      {stage && stage !== 'complete' && (
        <div className="card px-6">
          <ProgressBar stage={stage} />
        </div>
      )}

      {/* ── Error ── */}
      {error && (
        <div className="card px-5 py-4 mb-4 border-red-200 bg-red-50">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-red-700">Parse error</p>
              <p className="text-xs text-red-600 mt-0.5 break-words">{error}</p>
            </div>
          </div>
          {canParse && (
            <div className="mt-3 flex gap-2">
              <button
                onClick={handleParse}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg transition-colors"
              >
                <Brain className="w-3.5 h-3.5" /> Try Again
              </button>
              <button
                onClick={handleReset}
                className="flex items-center gap-1.5 px-3 py-1.5 border border-red-300 text-red-700 hover:bg-red-100 text-xs font-semibold rounded-lg transition-colors"
              >
                ← Start Over
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Results section ── */}
      {result && stage === 'complete' && (
        <>
          {/* Demo banner */}
          {demoMode && (
            <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl px-5 py-3 mb-4">
              <Info className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-amber-700">
                <strong>Demo mode</strong> — No API key configured or no files uploaded.
                Showing BID-106 sample data. Add <code>ANTHROPIC_API_KEY</code> to <code>.env</code> to enable live parsing.
              </p>
            </div>
          )}

          {/* Warnings */}
          {result.parsing_warnings?.filter(w => !w.toLowerCase().includes('demo')).map((w, i) => (
            <div key={i} className="flex items-start gap-3 bg-yellow-50 border border-yellow-200 rounded-xl px-5 py-2.5 mb-3">
              <AlertCircle className="w-4 h-4 text-yellow-600 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-yellow-700">{w}</p>
            </div>
          ))}

          {/* ─────── STEP 2: Bid Details Form ─────── */}
          <BidDetailsForm
            result={result}
            onSaved={handleSaved}
            onReset={handleReset}
          />

          {/* ─────── Parse Results card (below Step 2) ─────── */}
          <div className="card mb-6">
            {/* Tabs header */}
            <div className="flex items-center justify-between px-5 pt-4 pb-0 border-b border-gray-100">
              <div className="flex gap-1">
                <button
                  onClick={() => setActiveTab('items')}
                  className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-all ${
                    activeTab === 'items'
                      ? 'border-exl-orange text-exl-orange'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Line Items
                  <span className="ml-1.5 text-xs bg-exl-orange/10 text-exl-orange px-1.5 py-0.5 rounded-full font-semibold">
                    {result.line_items?.length ?? 0}
                  </span>
                </button>
                <button
                  onClick={() => setActiveTab('targeting')}
                  className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-all ${
                    activeTab === 'targeting'
                      ? 'border-exl-orange text-exl-orange'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Supplier Targeting
                </button>
              </div>
              {result.metadata?.parsing_confidence != null && (
                <div className="pb-2">
                  <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold ${
                    result.metadata.parsing_confidence >= 90 ? 'bg-emerald-100 text-emerald-700'
                    : result.metadata.parsing_confidence >= 75 ? 'bg-amber-100 text-amber-700'
                    : 'bg-red-100 text-red-700'
                  }`}>
                    <Brain className="w-3 h-3" />
                    {result.metadata.parsing_confidence}% confidence
                  </span>
                </div>
              )}
            </div>

            {/* Tab content */}
            <div className="p-0">
              {activeTab === 'items' && <LineItemsTab items={result.line_items || []} />}
              {activeTab === 'targeting' && (
                <div className="p-5">
                  <SupplierTargeting targeting={result.supplier_targeting} />
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* ── Toast ── */}
      {toast && <Toast message={toast.message} onDone={() => setToast(null)} />}

      {/* ── Unsaved files exit warning ── */}
      {blocker.state === 'blocked' && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-md rounded-2xl shadow-2xl overflow-hidden">
            <div className="px-6 pt-6 pb-4 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <h2 className="text-base font-bold text-exl-navy">Unsaved Files</h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  You have uploaded files that haven't been saved as a bid yet.
                </p>
              </div>
            </div>
            <div className="mx-6 mb-4 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 space-y-2">
              {pdfFile && (
                <div className="flex items-center gap-2.5 text-sm text-amber-900">
                  <FileText className="w-4 h-4 text-amber-600 flex-shrink-0" />
                  <span className="truncate font-medium">{pdfFile.name}</span>
                  <span className="text-amber-600 text-xs flex-shrink-0">— RFP Document</span>
                </div>
              )}
              {excelFile && (
                <div className="flex items-center gap-2.5 text-sm text-amber-900">
                  <FileSpreadsheet className="w-4 h-4 text-amber-600 flex-shrink-0" />
                  <span className="truncate font-medium">{excelFile.name}</span>
                  <span className="text-amber-600 text-xs flex-shrink-0">— Item List</span>
                </div>
              )}
            </div>
            <p className="px-6 pb-5 text-sm text-gray-600">
              If you leave now, your uploaded files and any parsed data will be lost.
            </p>
            <div className="px-6 pb-6 flex items-center gap-3">
              <button
                onClick={() => blocker.reset()}
                className="flex-1 py-2.5 px-4 text-sm font-semibold rounded-xl border-2 border-exl-navy text-exl-navy hover:bg-exl-navy/5 transition-colors"
              >
                Stay on Page
              </button>
              <button
                onClick={() => {
                  setBidSaved(true)   // disarm guard before proceeding
                  blocker.proceed()
                }}
                className="flex-1 py-2.5 px-4 text-sm font-semibold rounded-xl bg-red-600 hover:bg-red-700 text-white transition-colors"
              >
                Discard &amp; Leave →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
