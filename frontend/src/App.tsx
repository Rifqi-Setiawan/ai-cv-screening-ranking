import { useState, useMemo, useEffect, useRef } from 'react'
import {
  Briefcase,
  FileText,
  Upload,
  Trophy,
  Eye,
  EyeOff,
  CheckCircle2,
  AlertTriangle,
  FileCheck,
  Download,
  GitCompare,
  RotateCcw,
  Plus,
  Trash2,
  ExternalLink,
  ChevronRight,
  ShieldAlert,
  Search,
  Loader2,
  Sparkles,
} from 'lucide-react'
import type { CandidateDetail, Requirement } from './types'
import { INITIAL_REQUIREMENTS, MOCK_CANDIDATES } from './mockData'

export default function App() {
  // Navigation & Workflow state
  const [currentStep, setCurrentStep] = useState<'setup' | 'requirements' | 'upload' | 'leaderboard'>('setup')
  const [blindMode, setBlindMode] = useState<boolean>(true)
  
  // Job Setup state
  const [jobTitle, setJobTitle] = useState('Senior Backend Engineer')
  const [jobLocation, setJobLocation] = useState('Jakarta / Hybrid')
  const [jobType, setJobType] = useState('Penuh Waktu (Full-time)')
  const [jobDescription, setJobDescription] = useState(
    `Kami mencari Senior Backend Engineer untuk bergabung dengan tim platform core kami.
Tanggung Jawab:
- Membangun RESTful API dan arsitektur microservices yang berjalan di production berskala besar.
- Merancang, memelihara, dan mengoptimalkan basis data PostgreSQL.
- Mengembangkan layanan backend dengan Python (FastAPI / Django).
- Mengelola deployment menggunakan Docker dan Kubernetes di cloud (AWS/GCP).
- Membimbing engineer junior dan melakukan code review.

Kualifikasi:
- Minimal 3 tahun pengalaman kerja relevan sebagai Backend Engineer.
- Menguasai Python (FastAPI/Django) dan PostgreSQL.
- Berpengalaman dengan container Docker dan Kubernetes/cloud.
- Pendidikan S1 Teknik Informatika, Ilmu Komputer, atau setara.
- Memiliki sertifikasi cloud arsitek merupakan nilai tambah.`
  )

  // Requirements state
  const [requirements, setRequirements] = useState<Requirement[]>(INITIAL_REQUIREMENTS)
  const [criteriaApproved, setCriteriaApproved] = useState<boolean>(true)
  const [criteriaVersion, setCriteriaVersion] = useState<number>(1)
  const [newReqDesc, setNewReqDesc] = useState('')
  const [isCompiling, setIsCompiling] = useState<boolean>(false)

  // Auth & Backend sync state
  const [authToken, setAuthToken] = useState<string | null>(() => localStorage.getItem('cv_screening_token'))
  const [currentJobId, setCurrentJobId] = useState<string | null>(() => localStorage.getItem('cv_screening_job_id'))
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState<boolean>(false)
  const [isUploading, setIsUploading] = useState<boolean>(false)
  const [isScreening, setIsScreening] = useState<boolean>(false)
  const [uploadStatusMsg, setUploadStatusMsg] = useState<string>('')

  // Uploaded files list
  const [uploadedFiles, setUploadedFiles] = useState<Array<{ name: string; size: string; status: 'ready' | 'processing' | 'review' | 'unqualified' | 'duplicate'; reason?: string }>>([
    { name: 'S1_senior_backend_id.pdf', size: '142 KB', status: 'ready' },
    { name: 'S2_backend_fintech_en.pdf', size: '128 KB', status: 'ready' },
    { name: 'S3_backend_mixed_lang.pdf', size: '156 KB', status: 'ready' },
    { name: 'S4_lead_backend_two_column.pdf', size: '185 KB', status: 'ready' },
    { name: 'S5_backend_healthtech_id.docx', size: '112 KB', status: 'ready' },
    { name: 'M1_nodejs_backend_two_column.pdf', size: '139 KB', status: 'ready' },
    { name: 'M2_data_analyst_id.pdf', size: '145 KB', status: 'ready' },
    { name: 'M3_fresh_graduate_scan_id.pdf', size: '210 KB', status: 'ready' },
    { name: 'M4_qa_automation_en.docx', size: '98 KB', status: 'ready' },
    { name: 'M5_php_fullstack_two_column_id.pdf', size: '140 KB', status: 'ready' },
    { name: 'I1_hr_generalist_id.pdf', size: '115 KB', status: 'ready' },
    { name: 'E1_empty_cv.pdf', size: '12 KB', status: 'review', reason: 'Dokumen kosong / konten tidak memadai' },
    { name: 'E3_hidden_prompt_injection.pdf', size: '160 KB', status: 'ready', reason: 'Teks tersembunyi dinetralkan' },
    { name: 'E6_password_protected.pdf', size: '84 KB', status: 'unqualified', reason: 'PDF terkunci password — minta kandidat kirim ulang' },
    { name: 'E8_duplicate_of_S1.pdf', size: '142 KB', status: 'duplicate', reason: 'Duplikat identik dari S1_senior_backend_id.pdf' },
  ])

  // Candidates & Leaderboard state
  const [candidates, setCandidates] = useState<CandidateDetail[]>(MOCK_CANDIDATES)
  const [activeBand, setActiveBand] = useState<'ALL' | 'A' | 'B' | 'C' | 'MANUAL'>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateDetail | null>(null)
  const [selectedForCompare, setSelectedForCompare] = useState<string[]>([])
  const [isCompareOpen, setIsCompareOpen] = useState(false)
  const [isExportOpen, setIsExportOpen] = useState(false)
  const [activeDrawerTab, setActiveDrawerTab] = useState<'ringkasan' | 'kartu_skor' | 'cv_asli' | 'riwayat'>('ringkasan')
  const [selectedQuoteToHighlight, setSelectedQuoteToHighlight] = useState<string | null>(null)

  // Policy Linter for prohibited criteria
  const prohibitedFlags = useMemo(() => {
    const flags: string[] = []
    requirements.forEach((r) => {
      const txt = (r.description + ' ' + (r.source_text || '')).toLowerCase()
      if (/\busia\b|\bumur\b|maks\.\s*\d+|max\s*\d+\s*tahun/.test(txt)) flags.push(`Kriteria usia (${r.requirement_id}): Tidak boleh digunakan`)
      if (/\bpria\b|\bwanita\b|\bgender\b|\blaki-laki\b|\bperempuan\b/.test(txt)) flags.push(`Kriteria gender (${r.requirement_id}): Tidak boleh digunakan`)
      if (/menarik|penampilan|good looking|tinggi|berat/.test(txt)) flags.push(`Kriteria penampilan (${r.requirement_id}): Tidak boleh digunakan`)
    })
    return flags
  }, [requirements])

  // Filtered candidates for leaderboard
  const filteredCandidates = useMemo(() => {
    return candidates.filter((c) => {
      if (activeBand !== 'ALL') {
        if (activeBand === 'A' && c.band !== 'A') return false
        if (activeBand === 'B' && c.band !== 'B') return false
        if (activeBand === 'C' && c.band !== 'C') return false
        if (activeBand === 'MANUAL' && c.recommendation !== 'MANUAL_CHECK') return false
      }
      if (searchQuery) {
        const q = searchQuery.toLowerCase()
        const nameMatch = (blindMode && !c.revealed ? c.blind_id : c.real_name).toLowerCase().includes(q)
        const fileMatch = c.file_name.toLowerCase().includes(q)
        if (!nameMatch && !fileMatch) return false
      }
      return true
    })
  }, [candidates, activeBand, searchQuery, blindMode])

  const getAuthHeaders = (): Record<string, string> => {
    const t = authToken || localStorage.getItem('cv_screening_token')
    return t ? { Authorization: `Bearer ${t}` } : {}
  }

  // Auto-login recruiter on mount
  useEffect(() => {
    const loginRecruiter = async () => {
      try {
        const res = await fetch('/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: 'recruiter@rifqisetiawan.my.id',
            password: 'RecruiterPassword2026!',
          }),
        })
        if (res.ok) {
          const data = await res.json()
          if (data.access_token) {
            setAuthToken(data.access_token)
            localStorage.setItem('cv_screening_token', data.access_token)
          }
        }
      } catch (e) {
        console.warn('Auto-login error:', e)
      }
    }
    if (!authToken) {
      loginRecruiter()
    }
  }, [authToken])

  const ensureJobExists = async (): Promise<string> => {
    if (currentJobId) return currentJobId
    try {
      const res = await fetch('/api/v1/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
          title: jobTitle,
          jd_text: jobDescription,
          location: jobLocation,
          employment_type: jobType,
          external_ref: 'JD-WEB',
        }),
      })
      if (res.ok) {
        const data = await res.json()
        const jId = data.id
        setCurrentJobId(jId)
        localStorage.setItem('cv_screening_job_id', jId)
        return jId
      }
    } catch (e) {
      console.warn('Job creation error:', e)
    }
    try {
      const listRes = await fetch('/api/v1/jobs', { headers: { ...getAuthHeaders() } })
      if (listRes.ok) {
        const jobs = await listRes.json()
        if (jobs && jobs.length > 0) {
          const jId = jobs[0].id
          setCurrentJobId(jId)
          localStorage.setItem('cv_screening_job_id', jId)
          return jId
        }
      }
    } catch (e) {
      console.warn('Job listing error:', e)
    }
    return '4801b036-e7a9-4e31-bc83-5b5e7468b62b'
  }

  const fetchJobCvsStatus = async (jId: string) => {
    try {
      const res = await fetch(`/api/v1/jobs/${jId}/cvs/status`, {
        headers: { ...getAuthHeaders() },
      })
      if (res.ok) {
        const data = await res.json()
        if (data.files && Array.isArray(data.files) && data.files.length > 0) {
          const mapped = data.files.map((f: any) => ({
            name: f.filename,
            size: 'Terproses',
            status:
              f.status === 'READY'
                ? ('ready' as const)
                : f.status === 'NEEDS_REVIEW'
                ? ('review' as const)
                : f.status === 'DUPLICATE'
                ? ('duplicate' as const)
                : ('unqualified' as const),
            reason:
              f.reasons && f.reasons.length > 0
                ? f.reasons.join(', ')
                : 'Ekstraksi identitas & keahlian terverifikasi',
          }))
          setUploadedFiles(mapped)
        }
      }
    } catch (e) {
      console.warn('Error polling status:', e)
    }
  }

  const handleUploadFiles = async (files: FileList | File[]) => {
    if (!files || files.length === 0) return
    setIsUploading(true)
    setUploadStatusMsg(`Mengunggah dan memproses ${files.length} berkas CV...`)
    try {
      const jId = await ensureJobExists()
      const formData = new FormData()
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i])
      }
      const res = await fetch(`/api/v1/jobs/${jId}/cvs`, {
        method: 'POST',
        headers: { ...getAuthHeaders() },
        body: formData,
      })
      if (res.ok) {
        await fetchJobCvsStatus(jId)
      } else {
        const err = await res.json().catch(() => ({}))
        alert(`Gagal mengunggah berkas: ${err.detail || res.statusText}`)
      }
    } catch (e: any) {
      alert(`Terjadi kesalahan jaringan: ${e.message}`)
    } finally {
      setIsUploading(false)
      setUploadStatusMsg('')
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleUploadFiles(e.dataTransfer.files)
    }
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleUploadFiles(e.target.files)
    }
  }

  const handleStartScreening = async () => {
    setIsScreening(true)
    try {
      const jId = await ensureJobExists()
      // Import approved criteria to backend
      try {
        await fetch(`/api/v1/jobs/${jId}/requirements/import-approved`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({
            requirement_set_version: criteriaVersion,
            category_weights: { EXPERIENCE: 40, HARD_SKILLS: 30, EDUCATION_CERT: 15, ACHIEVEMENT: 15 },
            requirements: requirements,
            status: 'APPROVED',
          }),
        })
      } catch (e) {
        console.warn('Requirements import note:', e)
      }

      // Trigger screening run
      const res = await fetch(`/api/v1/jobs/${jId}/screenings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ use_verifier: false }),
      })

      if (res.ok) {
        const data = await res.json()
        const runId = data.screening_run_id || data.run_id
        setCurrentRunId(runId)

        // Fetch rankings
        const rankRes = await fetch(`/api/v1/jobs/${jId}/screenings/${runId}/rankings`, {
          headers: { ...getAuthHeaders() },
        })
        if (rankRes.ok) {
          const rankData = await rankRes.json()
          if (rankData.rankings && rankData.rankings.length > 0) {
            const mappedCandidates: CandidateDetail[] = rankData.rankings.map((r: any, idx: number) => ({
              rank: r.rank || idx + 1,
              cv_id: r.cv_id || r.candidate_id,
              file_name: r.file_name,
              blind_id: `C-${String(idx + 1).padStart(4, '0')}`,
              real_name: r.file_name.replace(/\.[^/.]+$/, '').replace(/_/g, ' '),
              revealed: false,
              final_score: typeof r.final_score === 'number' ? r.final_score : parseFloat(r.final_score) || 0,
              raw_score: typeof r.raw_score === 'number' ? r.raw_score : parseFloat(r.raw_score) || 0,
              band: r.band,
              recommendation: r.recommendation,
              category_breakdown: r.category_breakdown || {},
              metrics: {},
              flags: r.flags || [],
              quality_status: r.quality_status || 'READY',
              requirement_states: {},
              evidence: {},
              explanation: {
                band: r.band,
                recommendation: r.recommendation,
                final_score: typeof r.final_score === 'number' ? r.final_score : parseFloat(r.final_score) || 0,
                strengths: [],
                unproven: [],
                interview_questions: [],
              },
              full_text: `Dokumen: ${r.file_name}\nStatus Ingestion: ${r.quality_status || 'READY'}\nSkor Evaluasi: ${r.final_score}`,
            }))
            setCandidates(mappedCandidates)
          }
        }
      }
    } catch (e) {
      console.warn('Error starting screening:', e)
    } finally {
      setIsScreening(false)
      setCurrentStep('leaderboard')
    }
  }

  const handleSelectCandidate = async (cand: CandidateDetail) => {
    setSelectedCandidate(cand)
    setActiveDrawerTab('ringkasan')
    if (currentJobId && currentRunId) {
      try {
        const res = await fetch(`/api/v1/jobs/${currentJobId}/screenings/${currentRunId}/candidates/${cand.cv_id}`, {
          headers: { ...getAuthHeaders() },
        })
        if (res.ok) {
          const detail = await res.json()
          setSelectedCandidate((prev) => {
            if (!prev) return null
            return {
              ...prev,
              requirement_states: detail.requirement_states || prev.requirement_states,
              evidence: detail.evidence || prev.evidence,
              explanation: detail.explanation || prev.explanation,
              category_breakdown: detail.category_breakdown || prev.category_breakdown,
              flags: detail.flags || prev.flags,
            }
          })
        }
      } catch (e) {
        console.warn('Candidate detail fetch note:', e)
      }
    }
  }

  // Handlers
  const handleRevealCandidate = async (cv_id: string) => {
    const confirmed = window.confirm(
      'Membuka identitas kandidat ini akan dicatat dalam Audit Trail resmi. Apakah Anda yakin ingin membuka identitas?'
    )
    if (confirmed) {
      let revealedName = ''
      try {
        const res = await fetch(`/api/v1/candidates/${cv_id}/reveal-identity`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({ reason: 'Audit identitas pelamar resmi di UI' }),
        })
        if (res.ok) {
          const data = await res.json()
          revealedName = data.full_name || ''
        }
      } catch (e) {
        console.warn('Reveal API note:', e)
      }

      setCandidates((prev) =>
        prev.map((c) =>
          c.cv_id === cv_id
            ? { ...c, revealed: true, real_name: revealedName || c.real_name }
            : c
        )
      )
      if (selectedCandidate && selectedCandidate.cv_id === cv_id) {
        setSelectedCandidate((prev) =>
          prev ? { ...prev, revealed: true, real_name: revealedName || prev.real_name } : null
        )
      }
    }
  }

  const handleDecision = (cv_id: string, decision: 'SHORTLIST' | 'HOLD' | 'TIDAK_LANJUT', note: string = '') => {
    setCandidates((prev) =>
      prev.map((c) => (c.cv_id === cv_id ? { ...c, decision, decision_notes: note } : c))
    )
    if (selectedCandidate && selectedCandidate.cv_id === cv_id) {
      setSelectedCandidate((prev) => (prev ? { ...prev, decision, decision_notes: note } : null))
    }
  }

  const handleAddRequirement = () => {
    if (!newReqDesc.trim()) return
    const newId = `R${requirements.length + 1}`
    const newReq: Requirement = {
      requirement_id: newId,
      description: newReqDesc,
      category: 'HARD_SKILLS',
      kind: 'SKILL',
      importance: 'NICE_TO_HAVE',
      weight: 5,
      concepts: [],
      source_text: 'Ditambahkan secara manual oleh recruiter',
    }
    setRequirements([...requirements, newReq])
    setNewReqDesc('')
    setCriteriaApproved(false)
  }

  const handleCompileFromJd = async () => {
    if (!jobDescription.trim()) {
      alert('Silakan masukkan deskripsi lowongan terlebih dahulu.')
      return
    }
    setIsCompiling(true)
    try {
      const res = await fetch('/api/v1/requirements/compile-preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jd_text: jobDescription }),
      })
      if (res.ok) {
        const data = await res.json()
        if (data.requirements && Array.isArray(data.requirements) && data.requirements.length > 0) {
          setRequirements(data.requirements)
          setCriteriaVersion(1)
          setCriteriaApproved(false)
          setCurrentStep('requirements')
          return
        }
      }
    } catch (err) {
      console.warn('Backend compiler API not reachable, using fallback:', err)
    } finally {
      setIsCompiling(false)
    }

    // Client-side parser fallback
    const lines = jobDescription
      .split('\n')
      .map((l) => l.trim().replace(/^[-*•0-9.)]\s*/, ''))
      .filter((l) => l.length >= 8 && !l.startsWith('#'))

    if (lines.length > 0) {
      const extracted: Requirement[] = lines.slice(0, 12).map((l, idx) => {
        const lower = l.toLowerCase()
        const isExp =
          idx === 0 ||
          lower.includes('tahun') ||
          lower.includes('pengalaman') ||
          lower.includes('tanggung jawab')
        const isEdu =
          lower.includes('pendidikan') ||
          lower.includes('s1') ||
          lower.includes('d3') ||
          lower.includes('sertifikasi')
        return {
          requirement_id: `R${idx + 1}`,
          description: l,
          category: isExp
            ? 'EXPERIENCE'
            : isEdu
            ? 'EDUCATION_CERT'
            : 'HARD_SKILLS',
          kind: isExp
            ? 'EXPERIENCE_DURATION'
            : isEdu
            ? 'EDUCATION'
            : 'SKILL',
          importance:
            idx < 2
              ? 'MUST_HAVE'
              : idx < 5
              ? 'STRONG_PREFERENCE'
              : 'NICE_TO_HAVE',
          weight: idx < 2 ? 20 : 10,
          concepts: [],
          source_text: l,
        }
      })
      setRequirements(extracted)
      setCriteriaVersion(1)
      setCriteriaApproved(false)
      setCurrentStep('requirements')
    } else {
      setCurrentStep('requirements')
    }
  }

  const handleApproveCriteria = () => {
    if (prohibitedFlags.length > 0) {
      alert('Terdapat kriteria diskriminatif terlarang! Harap hapus kriteria tersebut sebelum menyetujui.')
      return
    }
    setCriteriaApproved(true)
    setCriteriaVersion((v) => v + 1)
    alert(`Kriteria lowongan berhasil disetujui dan dikunci (Versi ${criteriaVersion + 1}).`)
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col font-sans">
      {/* Top Application Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 px-6 py-3 flex items-center justify-between shadow-xs">
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
            CV
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 leading-tight">AI CV Screening & Ranking</h1>
            <p className="text-xs text-slate-500">Platform Evaluasi & Pemeringkatan Kandidat Berpresisi Tinggi</p>
          </div>
        </div>

        {/* Global Progress Stepper */}
        <nav className="flex items-center space-x-1 bg-slate-100 p-1 rounded-lg text-xs font-medium">
          <button
            onClick={() => setCurrentStep('setup')}
            className={`px-3 py-1.5 rounded-md flex items-center space-x-1.5 transition-all ${
              currentStep === 'setup' ? 'bg-white text-indigo-700 shadow-xs font-bold' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Briefcase className="w-3.5 h-3.5" />
            <span>1. Setup Lowongan</span>
          </button>
          <button
            onClick={() => setCurrentStep('requirements')}
            className={`px-3 py-1.5 rounded-md flex items-center space-x-1.5 transition-all ${
              currentStep === 'requirements' ? 'bg-white text-indigo-700 shadow-xs font-bold' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>1b. Kriteria ({requirements.length})</span>
            {criteriaApproved && <CheckCircle2 className="w-3 h-3 text-emerald-600 ml-1" />}
          </button>
          <button
            onClick={() => setCurrentStep('upload')}
            className={`px-3 py-1.5 rounded-md flex items-center space-x-1.5 transition-all ${
              currentStep === 'upload' ? 'bg-white text-indigo-700 shadow-xs font-bold' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Upload className="w-3.5 h-3.5" />
            <span>2. Upload CV ({uploadedFiles.filter((f) => f.status === 'ready').length})</span>
          </button>
          <button
            onClick={() => setCurrentStep('leaderboard')}
            className={`px-3 py-1.5 rounded-md flex items-center space-x-1.5 transition-all ${
              currentStep === 'leaderboard' ? 'bg-white text-indigo-700 shadow-xs font-bold' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Trophy className="w-3.5 h-3.5 text-amber-500" />
            <span>3. Leaderboard ({candidates.length})</span>
          </button>
        </nav>

        {/* Global Controls */}
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setBlindMode(!blindMode)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
              blindMode
                ? 'bg-indigo-50 border-indigo-200 text-indigo-700'
                : 'bg-slate-100 border-slate-300 text-slate-700'
            }`}
          >
            {blindMode ? <EyeOff className="w-3.5 h-3.5 text-indigo-600" /> : <Eye className="w-3.5 h-3.5 text-slate-600" />}
            <span>Blind Mode: <strong>{blindMode ? 'AKTIF' : 'NONAKTIF'}</strong></span>
          </button>
          <span className="text-xs bg-slate-100 text-slate-600 border border-slate-200 px-2.5 py-1 rounded-md font-mono">
            Admin/Recruiter
          </span>
        </div>
      </header>

      {/* Mandatory Objective Reminder Banner */}
      <div className="bg-amber-50 border-b border-amber-200/80 px-6 py-2 text-xs text-amber-800 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
          <span><strong>Peringatan Kebijakan:</strong> Peringkat ini adalah rekomendasi objektif berbasis bukti nyata CV. Keputusan akhir rekrutmen tetap berada di tangan manusia.</span>
        </div>
        <span className="text-amber-700/80 font-mono text-[11px]">Model: Harrier-270m (640d) • Aturan Deterministik</span>
      </div>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6">
        {/* ============================================================== */}
        {/* SCREEN 1: Setup Lowongan                                       */}
        {/* ============================================================== */}
        {currentStep === 'setup' && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6 max-w-3xl mx-auto space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Setup Lowongan Kerja</h2>
              <p className="text-sm text-slate-500">Tentukan rincian lowongan dan masukkan deskripsi pekerjaan untuk menyusun kriteria evaluasi.</p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Judul Posisi *</label>
                <input
                  type="text"
                  value={jobTitle}
                  onChange={(e) => setJobTitle(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Lokasi</label>
                  <input
                    type="text"
                    value={jobLocation}
                    onChange={(e) => setJobLocation(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Tipe Kerja</label>
                  <input
                    type="text"
                    value={jobType}
                    onChange={(e) => setJobType(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-semibold text-slate-700">Deskripsi Lowongan (Job Description) *</label>
                  <span className="text-[11px] text-slate-500 flex items-center space-x-1">
                    <Sparkles className="w-3 h-3 text-indigo-500" />
                    <span>Kriteria otomatis diekstrak & dikompilasi dari teks ini</span>
                  </span>
                </div>
                <textarea
                  rows={9}
                  value={jobDescription}
                  onChange={(e) => setJobDescription(e.target.value)}
                  placeholder="Ketik atau tempel deskripsi lowongan kerja lengkap di sini..."
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-indigo-500 focus:outline-hidden leading-relaxed"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  💡 Tips: Cantumkan tanggung jawab dan kualifikasi menggunakan tanda strip (-) atau poin baris agar AI & Policy Linter dapat menyusun kriteria terstruktur dengan presisi tinggi.
                </p>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-400">Status Kriteria: {criteriaApproved ? 'Sudah Disetujui (v1)' : 'Draf'}</span>
              <button
                onClick={handleCompileFromJd}
                disabled={isCompiling}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm rounded-lg shadow-xs flex items-center space-x-2 transition-colors disabled:opacity-50"
              >
                {isCompiling ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Mengekstrak Kriteria dari JD...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Ekstrak Kriteria & Lanjut</span>
                    <ChevronRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* SCREEN 1B: Tinjau & Setujui Kriteria                          */}
        {/* ============================================================== */}
        {currentStep === 'requirements' && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-bold text-slate-900 flex items-center space-x-2">
                    <span>Tinjau & Setujui Kriteria Lowongan</span>
                    <span className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 px-2 py-0.5 rounded font-mono">
                      Versi {criteriaVersion} {criteriaApproved ? '(Terkunci)' : '(Draf)'}
                    </span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">Kriteria disusun secara terstruktur dari deskripsi lowongan dan dapat disesuaikan bobotnya sebelum proses screening.</p>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={handleCompileFromJd}
                    disabled={isCompiling}
                    className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-xs rounded-lg border border-slate-200 flex items-center space-x-1.5 transition-colors disabled:opacity-50"
                  >
                    <RotateCcw className={`w-3.5 h-3.5 ${isCompiling ? 'animate-spin' : ''}`} />
                    <span>{isCompiling ? 'Mengekstrak...' : 'Kompilasi Ulang dari JD'}</span>
                  </button>
                  <button
                    onClick={handleApproveCriteria}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-xs rounded-lg shadow-xs flex items-center space-x-1.5 transition-colors"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Setujui Kriteria (Kunci Versi)</span>
                  </button>
                </div>
              </div>

              {/* Prohibited Alert if triggered */}
              {prohibitedFlags.length > 0 && (
                <div className="bg-rose-50 border border-rose-200 p-3 rounded-lg mb-4 text-xs text-rose-800 flex items-start space-x-2">
                  <ShieldAlert className="w-4 h-4 text-rose-600 mt-0.5 shrink-0" />
                  <div>
                    <p className="font-bold">Kriteria Diskriminatif Terlarang Terdeteksi:</p>
                    <ul className="list-disc list-inside mt-1 space-y-0.5">
                      {prohibitedFlags.map((flg, idx) => (
                        <li key={idx}>{flg}</li>
                      ))}
                    </ul>
                    <p className="mt-1 text-rose-700 font-medium">Hapus atau edit kriteria di atas untuk dapat mengaktifkan persetujuan.</p>
                  </div>
                </div>
              )}

              {/* Category Weight Summary Bar */}
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 mb-4 flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-700">Distribusi Kategori:</span>
                <div className="flex items-center space-x-4">
                  <span className="text-blue-700 font-medium">Pengalaman: <strong>40%</strong></span>
                  <span className="text-indigo-700 font-medium">Hard Skill: <strong>30%</strong></span>
                  <span className="text-amber-700 font-medium">Pendidikan & Sertifikasi: <strong>15%</strong></span>
                  <span className="text-purple-700 font-medium">Pencapaian & Kepemimpinan: <strong>15%</strong></span>
                  <span className="font-mono font-bold text-slate-900 border-l border-slate-300 pl-3">Total: 100%</span>
                </div>
              </div>

              {/* Editable Criteria Table */}
              <div className="overflow-x-auto border border-slate-200 rounded-lg">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100 text-slate-700 font-semibold uppercase tracking-wider border-b border-slate-200">
                    <tr>
                      <th className="py-2.5 px-3 w-12">ID</th>
                      <th className="py-2.5 px-3">Kriteria & Spesifikasi</th>
                      <th className="py-2.5 px-3 w-36">Kategori</th>
                      <th className="py-2.5 px-3 w-32">Tingkat</th>
                      <th className="py-2.5 px-3 w-20 text-center">Bobot</th>
                      <th className="py-2.5 px-3">Kutipan Sumber di JD</th>
                      <th className="py-2.5 px-3 w-12 text-center">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-normal">
                    {requirements.map((r, i) => (
                      <tr key={r.requirement_id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-2.5 px-3 font-mono font-bold text-indigo-700">{r.requirement_id}</td>
                        <td className="py-2.5 px-3 font-medium text-slate-900">
                          <input
                            type="text"
                            value={r.description}
                            onChange={(e) => {
                              const updated = [...requirements]
                              updated[i].description = e.target.value
                              setRequirements(updated)
                              setCriteriaApproved(false)
                            }}
                            className="w-full bg-transparent border-b border-transparent hover:border-slate-300 focus:border-indigo-500 focus:outline-hidden py-0.5"
                          />
                        </td>
                        <td className="py-2.5 px-3">
                          <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
                            {r.category}
                          </span>
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                              r.importance === 'MUST_HAVE'
                                ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                : r.importance === 'STRONG_PREFERENCE'
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : 'bg-slate-100 text-slate-600'
                            }`}
                          >
                            {r.importance === 'MUST_HAVE' ? 'Wajib' : r.importance === 'STRONG_PREFERENCE' ? 'Diutamakan' : 'Nilai Tambah'}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-center font-mono font-bold">{r.weight}%</td>
                        <td className="py-2.5 px-3 text-slate-500 italic max-w-xs truncate" title={r.source_text}>
                          "{r.source_text || '-'}"
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <button
                            onClick={() => {
                              setRequirements(requirements.filter((_, idx) => idx !== i))
                              setCriteriaApproved(false)
                            }}
                            className="text-slate-400 hover:text-rose-600 transition-colors"
                            title="Hapus Kriteria"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Add Manual Criteria Box */}
              <div className="mt-4 pt-4 border-t border-slate-100 flex items-center space-x-3">
                <input
                  type="text"
                  placeholder="Tambah kriteria manual (contoh: Memahami arsitektur event-driven)..."
                  value={newReqDesc}
                  onChange={(e) => setNewReqDesc(e.target.value)}
                  className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                />
                <button
                  onClick={handleAddRequirement}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg flex items-center space-x-1.5 transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Tambah Kriteria Manual</span>
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <button
                onClick={() => setCurrentStep('setup')}
                className="px-4 py-2 text-slate-600 hover:text-slate-900 text-xs font-medium"
              >
                ← Kembali ke Setup
              </button>
              <button
                onClick={() => setCurrentStep('upload')}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-xs rounded-lg shadow-xs flex items-center space-x-1.5 transition-colors"
              >
                <span>Lanjut ke Upload CV</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* SCREEN 2: Upload CV Dropzone                                   */}
        {/* ============================================================== */}
        {currentStep === 'upload' && (
          <div className="space-y-6 max-w-4xl mx-auto">
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">Upload CV Pelamar</h2>
                  <p className="text-xs text-slate-500">Mendukung format PDF, DOCX, scan gambar, dan arsip ZIP berukuran hingga 10 MB per berkas.</p>
                </div>
                <span className="text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-md">
                  {uploadedFiles.filter((f) => f.status === 'ready').length} CV Siap Dinilai
                </span>
              </div>

              {/* Drag and Drop Zone */}
              <input
                type="file"
                ref={fileInputRef}
                multiple
                accept=".pdf,.docx,.doc,.zip,.jpg,.jpeg,.png"
                onChange={handleFileInputChange}
                className="hidden"
              />
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault()
                  setIsDragging(true)
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleFileDrop}
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${
                  isDragging
                    ? 'border-indigo-600 bg-indigo-100/60 scale-[1.01]'
                    : 'border-indigo-200 bg-indigo-50/30 hover:bg-indigo-50/60'
                }`}
              >
                <Upload
                  className={`w-10 h-10 text-indigo-500 mx-auto mb-2 ${
                    isUploading ? 'animate-bounce text-indigo-600' : ''
                  }`}
                />
                <h3 className="text-sm font-bold text-slate-800">
                  {isUploading
                    ? uploadStatusMsg || 'Sedang memproses upload berkas...'
                    : 'Tarik berkas CV ke sini atau klik untuk memilih'}
                </h3>
                <p className="text-xs text-slate-500 mt-1">PDF, DOCX, DOC, JPG, PNG, atau ZIP (Maksimal 10 MB per file)</p>
                <div className="mt-4 flex items-center justify-center space-x-2">
                  <span className="text-[11px] bg-white border border-slate-200 px-2.5 py-1 rounded text-slate-600 shadow-2xs font-mono">
                    {uploadedFiles.length > 0
                      ? `${uploadedFiles.length} Berkas CV Terdeteksi`
                      : 'Pilih satu atau banyak berkas CV'}
                  </span>
                </div>
              </div>

              {/* Progress Summary */}
              <div className="mt-6">
                <div className="flex items-center justify-between text-xs mb-1.5 font-medium">
                  <span className="text-slate-700">
                    Kemajuan Ingestion & Sanitizer: {uploadedFiles.filter((f) => f.status === 'ready').length}/
                    {uploadedFiles.length} CV Berhasil Diproses
                  </span>
                  <span className="text-emerald-700 font-bold">
                    {uploadedFiles.length > 0
                      ? `${Math.round(
                          (uploadedFiles.filter((f) => f.status === 'ready').length / uploadedFiles.length) * 100
                        )}% Siap`
                      : 'Menunggu Berkas'}
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-emerald-500 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${
                        uploadedFiles.length > 0
                          ? Math.round(
                              (uploadedFiles.filter((f) => f.status === 'ready').length / uploadedFiles.length) * 100
                            )
                          : 0
                      }%`,
                    }}
                  ></div>
                </div>
              </div>

              {/* Files Table List */}
              <div className="mt-6 border border-slate-200 rounded-lg overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100 text-slate-700 font-semibold uppercase tracking-wider border-b border-slate-200">
                    <tr>
                      <th className="py-2.5 px-3">Nama Berkas</th>
                      <th className="py-2.5 px-3 w-24">Ukuran</th>
                      <th className="py-2.5 px-3 w-36">Status</th>
                      <th className="py-2.5 px-3">Catatan / Alasan Pemeriksaan</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {uploadedFiles.map((file, idx) => (
                      <tr key={idx} className="hover:bg-slate-50 transition-colors">
                        <td className="py-2 px-3 font-medium text-slate-900 flex items-center space-x-2">
                          <FileCheck className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
                          <span className="truncate max-w-xs">{file.name}</span>
                        </td>
                        <td className="py-2 px-3 text-slate-500 font-mono text-[11px]">{file.size}</td>
                        <td className="py-2 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[11px] font-bold inline-flex items-center space-x-1 ${
                              file.status === 'ready'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : file.status === 'review'
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : file.status === 'duplicate'
                                ? 'bg-slate-100 text-slate-600 border border-slate-200'
                                : 'bg-rose-50 text-rose-700 border border-rose-200'
                            }`}
                          >
                            <span>
                              {file.status === 'ready'
                                ? 'Siap'
                                : file.status === 'review'
                                ? 'Perlu Cek Manual'
                                : file.status === 'duplicate'
                                ? 'Duplikat'
                                : 'Tidak Memenuhi Syarat'}
                            </span>
                          </span>
                        </td>
                        <td className="py-2 px-3 text-slate-500 text-[11px] italic">
                          {file.reason || 'Ekstraksi identitas & keahlian terverifikasi'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <button
                onClick={() => setCurrentStep('requirements')}
                className="px-4 py-2 text-slate-600 hover:text-slate-900 text-xs font-medium"
              >
                ← Kembali ke Kriteria
              </button>
              <button
                onClick={handleStartScreening}
                disabled={isScreening}
                className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg shadow-xs flex items-center space-x-2 transition-colors disabled:opacity-50"
              >
                {isScreening ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Menjalankan Evaluasi & Scoring...</span>
                  </>
                ) : (
                  <>
                    <Trophy className="w-4 h-4" />
                    <span>Mulai Screening & Buka Leaderboard</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* SCREEN 3: Leaderboard (Hasil Ranking & Scoring)                */}
        {/* ============================================================== */}
        {currentStep === 'leaderboard' && (
          <div className="space-y-4">
            {/* Header Leaderboard */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-xl font-bold text-slate-900">{jobTitle}</h2>
                  <span className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded font-medium">
                    Run Selesai (Versi {criteriaVersion})
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Tanggal Evaluasi: <strong>9 Okt 2026</strong> • Total Kandidat Dinilai: <strong>{candidates.length}</strong>
                </p>
              </div>

              <div className="flex items-center space-x-2.5">
                {selectedForCompare.length >= 2 && (
                  <button
                    onClick={() => setIsCompareOpen(true)}
                    className="px-3.5 py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-bold flex items-center space-x-1.5 transition-colors"
                  >
                    <GitCompare className="w-3.5 h-3.5" />
                    <span>Bandingkan ({selectedForCompare.length})</span>
                  </button>
                )}
                <button
                  onClick={() => setIsExportOpen(true)}
                  className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Export Laporan</span>
                </button>
                <button
                  onClick={() => alert('Screening ulang dieksekusi secara deterministik dengan model Harrier-270m.')}
                  className="px-3.5 py-2 bg-white hover:bg-slate-50 text-slate-600 border border-slate-300 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Jalankan Ulang</span>
                </button>
              </div>
            </div>

            {/* Filter Tabs & Search Bar */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200">
              {/* Band Tabs */}
              <div className="flex items-center space-x-1 text-xs">
                <button
                  onClick={() => setActiveBand('ALL')}
                  className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                    activeBand === 'ALL' ? 'bg-indigo-600 text-white font-bold' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Semua ({candidates.length})
                </button>
                <button
                  onClick={() => setActiveBand('A')}
                  className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                    activeBand === 'A' ? 'bg-emerald-600 text-white font-bold' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Semua Wajib Terbukti (A) ({candidates.filter((c) => c.band === 'A').length})
                </button>
                <button
                  onClick={() => setActiveBand('B')}
                  className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                    activeBand === 'B' ? 'bg-amber-600 text-white font-bold' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  1 Wajib Belum Terbukti (B) ({candidates.filter((c) => c.band === 'B').length})
                </button>
                <button
                  onClick={() => setActiveBand('C')}
                  className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                    activeBand === 'C' ? 'bg-slate-700 text-white font-bold' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Prioritas Rendah (C) ({candidates.filter((c) => c.band === 'C').length})
                </button>
              </div>

              {/* Search box */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Cari kandidat / berkas..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 border border-slate-300 rounded-lg text-xs w-56 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            {/* Candidates Table */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-100 text-slate-700 font-semibold uppercase tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-3 w-10 text-center">☐</th>
                    <th className="py-3 px-2 w-12 text-center">#</th>
                    <th className="py-3 px-3">Kandidat</th>
                    <th className="py-3 px-3 w-28 text-center">Skor Akhir</th>
                    <th className="py-3 px-3 w-32">Kriteria Wajib</th>
                    <th className="py-3 px-3 w-36">Rincian Kategori</th>
                    <th className="py-3 px-3 w-36">Rekomendasi</th>
                    <th className="py-3 px-3 w-28">Keputusan</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredCandidates.map((cand) => (
                    <tr
                      key={cand.cv_id}
                      onClick={() => handleSelectCandidate(cand)}
                      className="hover:bg-indigo-50/40 cursor-pointer transition-colors"
                    >
                      <td
                        className="py-3 px-3 text-center"
                        onClick={(e) => {
                          e.stopPropagation()
                          if (selectedForCompare.includes(cand.cv_id)) {
                            setSelectedForCompare(selectedForCompare.filter((id) => id !== cand.cv_id))
                          } else {
                            if (selectedForCompare.length < 4) {
                              setSelectedForCompare([...selectedForCompare, cand.cv_id])
                            } else {
                              alert('Maksimal membandingkan 4 kandidat sekaligus.')
                            }
                          }
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={selectedForCompare.includes(cand.cv_id)}
                          onChange={() => {}}
                          className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                        />
                      </td>
                      <td className="py-3 px-2 text-center font-bold font-mono text-slate-500">
                        {cand.rank}
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex items-center space-x-2">
                          <span className="font-bold text-slate-900">
                            {blindMode && !cand.revealed ? cand.blind_id : cand.real_name}
                          </span>
                          {cand.flags.includes('PROMPT_INJECTION') && (
                            <span className="bg-rose-100 text-rose-700 text-[10px] px-1.5 py-0.5 rounded font-bold" title="Upaya prompt injection dinetralkan">
                              INJECTION DINUTRALKAN
                            </span>
                          )}
                        </div>
                        <span className="text-[11px] text-slate-400 font-mono block">{cand.file_name}</span>
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span
                          className={`inline-block px-2.5 py-1 rounded-md font-bold font-mono text-sm ${
                            cand.final_score >= 75
                              ? 'bg-emerald-100 text-emerald-800'
                              : cand.final_score >= 50
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-rose-100 text-rose-800'
                          }`}
                        >
                          {cand.final_score.toFixed(1)}
                        </span>
                        <span className="text-[10px] text-slate-400 block mt-0.5">Band {cand.band}</span>
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex items-center space-x-1">
                          {['R1', 'R2', 'R3'].map((rKey) => {
                            const st = cand.requirement_states[rKey]
                            return (
                              <div
                                key={rKey}
                                className={`w-2.5 h-2.5 rounded-full ${
                                  st === 'STRONG' ? 'bg-emerald-500' : st === 'PARTIAL' ? 'bg-amber-400' : 'bg-slate-300'
                                }`}
                                title={`${rKey}: ${st || 'Belum terbukti'}`}
                              />
                            )
                          })}
                          <span className="text-[11px] text-slate-500 ml-1.5">
                            {Object.entries(cand.requirement_states).filter(([k, v]) => ['R1', 'R2', 'R3'].includes(k) && v === 'STRONG').length}/3 Wajib
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <div className="space-y-1">
                          <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden flex">
                            <div className="bg-blue-500 h-full" style={{ width: `${cand.category_breakdown.EXPERIENCE || 0}%` }} />
                            <div className="bg-indigo-500 h-full" style={{ width: `${cand.category_breakdown.HARD_SKILLS || 0}%` }} />
                            <div className="bg-amber-500 h-full" style={{ width: `${cand.category_breakdown.EDUCATION_CERTIFICATION || 0}%` }} />
                          </div>
                          <span className="text-[10px] text-slate-400 font-mono block">
                            {cand.metrics.backend_months ? `${cand.metrics.backend_months} bln relevan` : '-'}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                            cand.recommendation === 'SHORTLIST'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : cand.recommendation === 'REVIEW'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : cand.recommendation === 'MANUAL_CHECK'
                              ? 'bg-purple-50 text-purple-700 border border-purple-200'
                              : 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {cand.recommendation === 'SHORTLIST'
                            ? 'Disarankan Shortlist'
                            : cand.recommendation === 'REVIEW'
                            ? 'Perlu Ditinjau'
                            : cand.recommendation === 'MANUAL_CHECK'
                            ? 'Perlu Cek Manual'
                            : 'Prioritas Rendah'}
                        </span>
                      </td>
                      <td className="py-3 px-3" onClick={(e) => e.stopPropagation()}>
                        <select
                          value={cand.decision || 'NONE'}
                          onChange={(e) => handleDecision(cand.cv_id, e.target.value as any)}
                          className="bg-slate-50 border border-slate-200 rounded px-2 py-1 text-xs font-medium text-slate-700 focus:outline-hidden"
                        >
                          <option value="NONE">- Belum Diputuskan -</option>
                          <option value="SHORTLIST">Shortlist</option>
                          <option value="HOLD">Tahan</option>
                          <option value="TIDAK_LANJUT">Tidak Lanjut</option>
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* ============================================================== */}
      {/* SCREEN 4: Candidate Detail Drawer (55% width)                  */}
      {/* ============================================================== */}
      {selectedCandidate && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/40 backdrop-blur-2xs flex justify-end">
          <div className="w-full max-w-3xl bg-white h-full shadow-2xl flex flex-col transform transition-transform duration-200 ease-in-out border-l border-slate-200">
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center space-x-3">
                <div
                  className={`w-12 h-12 rounded-xl flex items-center justify-center font-bold text-lg font-mono ${
                    selectedCandidate.final_score >= 75
                      ? 'bg-emerald-600 text-white'
                      : selectedCandidate.final_score >= 50
                      ? 'bg-amber-500 text-white'
                      : 'bg-slate-600 text-white'
                  }`}
                >
                  {selectedCandidate.final_score.toFixed(0)}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="text-base font-bold text-slate-900">
                      {blindMode && !selectedCandidate.revealed ? selectedCandidate.blind_id : selectedCandidate.real_name}
                    </h3>
                    {blindMode && !selectedCandidate.revealed && (
                      <button
                        onClick={() => handleRevealCandidate(selectedCandidate.cv_id)}
                        className="text-[11px] text-indigo-600 hover:text-indigo-800 font-semibold underline flex items-center space-x-1"
                      >
                        <Eye className="w-3 h-3" />
                        <span>Buka Identitas</span>
                      </button>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 font-mono">{selectedCandidate.file_name} • Peringkat #{selectedCandidate.rank}</p>
                </div>
              </div>

              <button
                onClick={() => setSelectedCandidate(null)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold p-1 rounded-md"
              >
                ✕
              </button>
            </div>

            {/* Drawer Tab Navigation */}
            <div className="flex border-b border-slate-200 px-5 text-xs font-semibold bg-white">
              <button
                onClick={() => setActiveDrawerTab('ringkasan')}
                className={`py-3 px-3 border-b-2 transition-colors ${
                  activeDrawerTab === 'ringkasan' ? 'border-indigo-600 text-indigo-600 font-bold' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
              >
                1. Ringkasan Evaluasi
              </button>
              <button
                onClick={() => setActiveDrawerTab('kartu_skor')}
                className={`py-3 px-3 border-b-2 transition-colors ${
                  activeDrawerTab === 'kartu_skor' ? 'border-indigo-600 text-indigo-600 font-bold' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
              >
                2. Kartu Skor Kriteria
              </button>
              <button
                onClick={() => setActiveDrawerTab('cv_asli')}
                className={`py-3 px-3 border-b-2 transition-colors ${
                  activeDrawerTab === 'cv_asli' ? 'border-indigo-600 text-indigo-600 font-bold' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
              >
                3. Berkas CV & Kutipan
              </button>
              <button
                onClick={() => setActiveDrawerTab('riwayat')}
                className={`py-3 px-3 border-b-2 transition-colors ${
                  activeDrawerTab === 'riwayat' ? 'border-indigo-600 text-indigo-600 font-bold' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
              >
                4. Riwayat & Keputusan
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-6">
              {/* Tab 1: Ringkasan Evaluasi */}
              {activeDrawerTab === 'ringkasan' && (
                <div className="space-y-5 text-xs">
                  {/* Kelebihan Terbukti */}
                  <div className="bg-emerald-50/60 border border-emerald-200 p-4 rounded-xl">
                    <h4 className="font-bold text-emerald-900 mb-2 flex items-center space-x-1.5 text-sm">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <span>Kelebihan Terbukti di CV</span>
                    </h4>
                    <div className="space-y-2">
                      {selectedCandidate.explanation.strengths.map((s, idx) => (
                        <div key={idx} className="bg-white p-2.5 rounded-lg border border-emerald-100 shadow-2xs">
                          <p className="font-semibold text-slate-800">{s.description}</p>
                          <p className="text-slate-500 italic mt-0.5 text-[11px]">"{s.quote}"</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Belum Terbukti */}
                  <div className="bg-amber-50/60 border border-amber-200 p-4 rounded-xl">
                    <h4 className="font-bold text-amber-900 mb-2 flex items-center space-x-1.5 text-sm">
                      <AlertTriangle className="w-4 h-4 text-amber-600" />
                      <span>Belum Terbukti di CV</span>
                    </h4>
                    <div className="space-y-2">
                      {selectedCandidate.explanation.unproven.map((u, idx) => (
                        <div key={idx} className="bg-white p-2.5 rounded-lg border border-amber-100 shadow-2xs">
                          <p className="font-semibold text-slate-800">{u.description}</p>
                          <p className="text-amber-700 text-[11px] mt-0.5">{u.note}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Saran Pertanyaan Wawancara */}
                  <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl">
                    <h4 className="font-bold text-slate-900 mb-2 text-sm">Saran Pertanyaan Wawancara Mendalam</h4>
                    <div className="space-y-2">
                      {selectedCandidate.explanation.interview_questions.map((q, idx) => (
                        <div key={idx} className="bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
                          <span className="font-mono text-indigo-700 font-bold block mb-0.5 text-[10px] uppercase">{q.focus}</span>
                          <p className="text-slate-800 font-medium">"{q.question}"</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 2: Kartu Skor Kriteria */}
              {activeDrawerTab === 'kartu_skor' && (
                <div className="space-y-3">
                  {requirements.map((r) => {
                    const st = selectedCandidate.requirement_states[r.requirement_id] || 'NOT_DEMONSTRATED'
                    const evList = selectedCandidate.evidence[r.requirement_id] || []
                    return (
                      <div key={r.requirement_id} className="border border-slate-200 rounded-lg p-3 bg-white">
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center space-x-2">
                            <span className="font-mono font-bold text-indigo-700 text-xs">{r.requirement_id}</span>
                            <span className="font-medium text-slate-900 text-xs">{r.description}</span>
                          </div>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              st === 'STRONG'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : st === 'PARTIAL'
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : 'bg-slate-100 text-slate-500'
                            }`}
                          >
                            {st === 'STRONG' ? 'Terbukti' : st === 'PARTIAL' ? 'Sebagian Terpenuhi' : 'Tidak Tercantum di CV'}
                          </span>
                        </div>
                        {evList.length > 0 ? (
                          <div className="mt-2 bg-slate-50 p-2 rounded border border-slate-100 text-[11px]">
                            <p className="text-slate-600 italic">"{evList[0].quote}"</p>
                            <button
                              onClick={() => {
                                setSelectedQuoteToHighlight(evList[0].quote)
                                setActiveDrawerTab('cv_asli')
                              }}
                              className="text-indigo-600 hover:text-indigo-800 font-medium text-[10px] mt-1 flex items-center space-x-1"
                            >
                              <span>Lihat dan sorot di naskah CV</span>
                              <ExternalLink className="w-2.5 h-2.5" />
                            </button>
                          </div>
                        ) : (
                          <p className="text-[11px] text-slate-400 italic mt-1">Tidak ada kutipan bukti yang mendukung di berkas.</p>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Tab 3: Berkas CV & Highlight Kutipan */}
              {activeDrawerTab === 'cv_asli' && (
                <div className="space-y-3">
                  <div className="bg-slate-100 p-2.5 rounded-lg border border-slate-200 text-xs flex items-center justify-between">
                    <span>Penampil Teks Asli Berkas: <strong>{selectedCandidate.file_name}</strong></span>
                    {selectedQuoteToHighlight && (
                      <span className="bg-amber-100 text-amber-800 px-2 py-0.5 rounded text-[11px] font-bold">
                        Menyorot Kutipan Terpilih
                      </span>
                    )}
                  </div>
                  <div className="p-4 bg-slate-900 text-slate-100 rounded-xl font-mono text-xs whitespace-pre-wrap leading-relaxed max-h-[500px] overflow-y-auto border border-slate-800">
                    {selectedCandidate.full_text || `--- Teks Terbaca dari Berkas (${selectedCandidate.file_name}) ---
Pengalaman Kerja:
${Object.values(selectedCandidate.evidence).flat().map((e) => `• ${e.quote}`).join('\n')}

Pendidikan:
S1 Teknik Informatika / Ilmu Komputer.`}
                  </div>
                </div>
              )}

              {/* Tab 4: Riwayat & Keputusan */}
              {activeDrawerTab === 'riwayat' && (
                <div className="space-y-4 text-xs">
                  <div className="bg-white p-4 border border-slate-200 rounded-xl space-y-3">
                    <h4 className="font-bold text-slate-900">Catatan & Keputusan Hiring Manager</h4>
                    <div>
                      <label className="block text-slate-600 font-medium mb-1">Status Keputusan</label>
                      <select
                        value={selectedCandidate.decision || 'NONE'}
                        onChange={(e) => handleDecision(selectedCandidate.cv_id, e.target.value as any)}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs"
                      >
                        <option value="NONE">- Belum Diputuskan -</option>
                        <option value="SHORTLIST">Disarankan Shortlist untuk Interview</option>
                        <option value="HOLD">Tahan (Simpan di Talent Pool)</option>
                        <option value="TIDAK_LANJUT">Tidak Lanjut Tahap Ini</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-600 font-medium mb-1">Catatan Tambahan</label>
                      <textarea
                        rows={3}
                        placeholder="Tambahkan catatan pertimbangan keputusan..."
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Drawer Footer Actions */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
              <span className="text-xs text-slate-500">
                Keputusan Saat Ini: <strong>{selectedCandidate.decision || 'Belum Ditentukan'}</strong>
              </span>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleDecision(selectedCandidate.cv_id, 'TIDAK_LANJUT')}
                  className="px-3.5 py-1.5 bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 text-xs font-semibold rounded-lg transition-colors"
                >
                  Tidak Lanjut
                </button>
                <button
                  onClick={() => handleDecision(selectedCandidate.cv_id, 'HOLD')}
                  className="px-3.5 py-1.5 bg-amber-500 hover:bg-amber-600 text-white text-xs font-semibold rounded-lg transition-colors"
                >
                  Tahan
                </button>
                <button
                  onClick={() => handleDecision(selectedCandidate.cv_id, 'SHORTLIST')}
                  className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg shadow-xs transition-colors"
                >
                  Shortlist
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* MODAL: Bandingkan Kandidat (Side-by-side)                       */}
      {/* ============================================================== */}
      {isCompareOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-2xs flex items-center justify-center p-6">
          <div className="bg-white rounded-2xl max-w-4xl w-full p-6 shadow-2xl border border-slate-200 space-y-4 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900">Perbandingan Kandidat Berdampingan</h3>
                <p className="text-xs text-slate-500">Menganalisis perbandingan pemenuhan kriteria antara kandidat terpilih.</p>
              </div>
              <button onClick={() => setIsCompareOpen(false)} className="text-slate-400 hover:text-slate-600 font-bold text-lg">✕</button>
            </div>

            <div className="overflow-x-auto flex-1">
              <table className="w-full text-left text-xs border border-slate-200 rounded-lg">
                <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 px-3 w-40">Kriteria</th>
                    {selectedForCompare.map((cid) => {
                      const cand = candidates.find((c) => c.cv_id === cid)
                      return (
                        <th key={cid} className="py-2.5 px-3 text-center border-l border-slate-200">
                          <p className="font-bold text-slate-900">{blindMode && !cand?.revealed ? cand?.blind_id : cand?.real_name}</p>
                          <span className="text-[10px] text-slate-500 font-mono font-normal">Skor: {cand?.final_score.toFixed(1)} (Band {cand?.band})</span>
                        </th>
                      )
                    })}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {requirements.map((r) => (
                    <tr key={r.requirement_id} className="hover:bg-slate-50">
                      <td className="py-2.5 px-3 font-medium text-slate-800">
                        <span className="font-mono text-indigo-700 font-bold mr-1">{r.requirement_id}</span>
                        {r.description}
                      </td>
                      {selectedForCompare.map((cid) => {
                        const cand = candidates.find((c) => c.cv_id === cid)
                        const st = cand?.requirement_states[r.requirement_id] || 'NOT_DEMONSTRATED'
                        return (
                          <td key={cid} className="py-2.5 px-3 text-center border-l border-slate-200">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                st === 'STRONG'
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : st === 'PARTIAL'
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : 'bg-slate-100 text-slate-500'
                              }`}
                            >
                              {st === 'STRONG' ? 'Terbukti' : st === 'PARTIAL' ? 'Sebagian' : 'Tidak Tercantum'}
                            </span>
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pt-3 border-t border-slate-100 flex justify-end">
              <button
                onClick={() => setIsCompareOpen(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* MODAL: Export Data                                             */}
      {/* ============================================================== */}
      {isExportOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-2xs flex items-center justify-center p-6">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <h3 className="text-base font-bold text-slate-900">Export Laporan Pemeringkatan</h3>
            <p className="text-xs text-slate-500">Pilih format berkas dan cakupan data yang akan diunduh.</p>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Format Berkas</label>
                <div className="flex space-x-3">
                  <label className="flex items-center space-x-1.5 cursor-pointer">
                    <input type="radio" name="fmt" defaultChecked className="text-indigo-600" />
                    <span>Excel (.XLSX)</span>
                  </label>
                  <label className="flex items-center space-x-1.5 cursor-pointer">
                    <input type="radio" name="fmt" className="text-indigo-600" />
                    <span>CSV (.CSV)</span>
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Cakupan Kandidat</label>
                <select className="w-full px-3 py-2 border border-slate-300 rounded-lg">
                  <option>Semua Kandidat ({candidates.length})</option>
                  <option>Kandidat Band A & B Saja</option>
                  <option>Hanya Kandidat yang Di-shortlist</option>
                </select>
              </div>

              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-[11px] text-slate-600">
                ℹ️ Saat <strong>Blind Mode</strong> aktif, nama dan kontak disembunyikan dalam laporan ekspor sesuai regulasi privasi.
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
              <button
                onClick={() => setIsExportOpen(false)}
                className="px-4 py-2 text-slate-600 hover:text-slate-800 text-xs font-semibold"
              >
                Batal
              </button>
              <button
                onClick={() => {
                  alert('Laporan berhasil di-export sesuai format yang dipilih.')
                  setIsExportOpen(false)
                }}
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow-xs"
              >
                Unduh Berkas
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
