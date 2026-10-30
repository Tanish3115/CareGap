"use client";

import { useCallback, useEffect, useState, FormEvent } from "react";
import { request, api } from "@/lib/api";
import { User, MedicalDocument, PatientProfile, DocumentType } from "@/types";
import { DocumentCard } from "./DocumentCard";
import { DocumentUploadModal } from "./DocumentUploadModal";
import { formatDate } from "@/lib/utils";

type AccessRequest = { id: string; doctor_name: string; organization: string | null; purpose: string; scope: string; duration_hours: number; allow_upload: boolean; status: string };
type Grant = { id: string; doctor_name: string; scope: string; valid_until: string; active: boolean; is_revoked: boolean; document_ids: string[] | null; allow_upload: boolean };
type Audit = { id: string; action: string; resource_type: string; created_at: string; actor_name?: string };
type Doctor = { id: string; full_name: string; license_number: string; specialization: string; verification_status: string };
type Person = { id: string; full_name: string; upload_types: DocumentType[] };
type CurrentUser = User & { patient?: { id: string; patient_code: string }; doctor?: { verification_status: string } };
const field = "w-full rounded-lg border border-slate-300 bg-white p-2 text-sm";
const button = "rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 hover:bg-blue-700";

export function CareWorkspace({ user }: { user: CurrentUser }) {
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [patients, setPatients] = useState<Person[]>([]);
  const [documents, setDocuments] = useState<MedicalDocument[]>([]);
  const [selected, setSelected] = useState("");
  const [patientId, setPatientId] = useState("");
  const [purpose, setPurpose] = useState("");
  const [scope, setScope] = useState("all");
  const [hours, setHours] = useState(24);
  const [upload, setUpload] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [evidence, setEvidence] = useState<Record<string, string>>({});
  const [recordSelections, setRecordSelections] = useState<Record<string, string[]>>({});
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  const load = useCallback(async () => {
    if (user.role === "patient") {
      const [r, g, a, docs] = await Promise.all([request<AccessRequest[]>("/consent/requests"), request<Grant[]>("/consent/grants"), request<Audit[]>("/consent/audit"), api.documents.list()]);
      setRequests(r); setGrants(g); setAudit(a); setDocuments(docs);
      setProfile(await api.patients.getProfile());
    } else if (user.role === "doctor" && user.doctor?.verification_status === "verified") {
      const [r, p] = await Promise.all([request<AccessRequest[]>("/consent/requests"), request<Person[]>("/consent/patients")]);
      setRequests(r); setPatients(p);
    } else if (user.role === "admin") {
      const [d, a] = await Promise.all([request<Doctor[]>("/admin/doctors"), request<Audit[]>("/admin/audit")]);
      setDoctors(d); setAudit(a);
    }
  }, [user.role, user.doctor?.verification_status]);

  useEffect(() => { load().catch(e => setError(e.message)).finally(() => setLoading(false)); }, [load]);

  const act = async (fn: () => Promise<unknown>, success: string) => {
    setBusy(true); setError(""); setMessage("");
    try { await fn(); await load(); setMessage(success); }
    catch (e) { setError(e instanceof Error ? e.message : "Operation failed"); }
    finally { setBusy(false); }
  };

  const sendRequest = (event: FormEvent) => {
    event.preventDefault();
    void act(() => request("/consent/requests", { method: "POST", body: JSON.stringify({ patient_id: patientId, purpose, scope, duration_hours: hours, allow_upload: upload }) }), "Access requested. The patient must approve before records are available.");
  };

  if (loading) return <p role="status" className="p-6 text-slate-600">Loading care workspace…</p>;
  return <section className="space-y-6" aria-label="Care workspace">
    <div><h2 className="text-xl font-bold text-slate-900">{user.role === "patient" ? "Sharing & access history" : user.role === "doctor" ? "Clinician workspace" : "Platform operations"}</h2>
      <p className="mt-1 text-sm text-slate-600">{user.role === "admin" ? "Professional verification and operational metadata. Clinical records require a patient-authorized clinical role." : "Consent is time-limited. Revocation blocks future requests; it cannot remove copies already downloaded."}</p></div>
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</p>}
    {message && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{message}</p>}

    {user.role === "patient" && <>
      {profile && <details className="rounded-xl border bg-white p-5"><summary className="cursor-pointer font-semibold">Edit your health profile</summary><form className="mt-4 grid gap-4 md:grid-cols-2" onSubmit={event => { event.preventDefault(); void act(() => api.patients.updateProfile({ date_of_birth: profile.date_of_birth || null, gender: profile.gender || null, blood_group: profile.blood_group || null, emergency_contact: profile.emergency_contact || null, address: profile.address || null }), "Profile updated."); }}>
        <label className="text-sm">Date of birth<input type="date" value={profile.date_of_birth || ""} onChange={e => setProfile({ ...profile, date_of_birth: e.target.value })} className={field} /></label>
        <label className="text-sm">Gender<input maxLength={20} value={profile.gender || ""} onChange={e => setProfile({ ...profile, gender: e.target.value })} className={field} /></label>
        <label className="text-sm">Blood group<select value={profile.blood_group || ""} onChange={e => setProfile({ ...profile, blood_group: e.target.value })} className={field}><option value="">Not recorded</option>{["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map(g => <option key={g}>{g}</option>)}</select></label>
        <label className="text-sm">Emergency contact<input maxLength={100} value={profile.emergency_contact || ""} onChange={e => setProfile({ ...profile, emergency_contact: e.target.value })} className={field} /></label>
        <label className="text-sm md:col-span-2">Address<textarea maxLength={2000} value={profile.address || ""} onChange={e => setProfile({ ...profile, address: e.target.value })} className={field} /></label><button disabled={busy} className={button}>Save profile</button>
      </form></details>}
      <div className="rounded-xl border bg-white p-5"><h3 className="font-semibold">Your patient ID</h3><p className="mt-2 font-mono text-xl font-bold tracking-wider">{user.patient?.patient_code}</p><p className="mt-2 text-xs text-slate-500">Share this short ID with your clinician to receive an access request. You still decide whether to approve access.</p></div>
      <div className="space-y-3"><h3 className="font-semibold">Access requests</h3>{requests.length === 0 && <p className="text-sm text-slate-500">No access requests.</p>}
        {requests.map(r => <article key={r.id} className="space-y-3 rounded-xl border bg-white p-5">
          <p className="font-semibold">{r.doctor_name} <span className="text-xs text-slate-500">· {r.status}</span></p>
          <p className="text-sm text-slate-600">Organization: {r.organization || "Not recorded"} (self-reported affiliation)</p>
          <p className="text-sm">Purpose: {r.purpose}</p><p className="text-sm">Scope: {r.scope.replaceAll("_", " ")} · {r.duration_hours} hours · {r.allow_upload ? "Read and upload" : "Read only"}</p>
          {r.status === "pending" && <>
            {!r.allow_upload && <fieldset className="space-y-2 text-sm"><legend className="font-medium">Optionally restrict to selected records (leave unchecked to share this document category)</legend>
              {documents.filter(d => r.scope === "all" || d.document_type === (r.scope === "labs_only" ? "lab_report" : "prescription")).map(d => <label key={d.id} className="flex gap-2"><input type="checkbox" checked={(recordSelections[r.id] || []).includes(d.id)} onChange={e => setRecordSelections(prev => ({ ...prev, [r.id]: e.target.checked ? [...(prev[r.id] || []), d.id] : (prev[r.id] || []).filter(id => id !== d.id) }))} />{d.title}</label>)}
            </fieldset>}
            <div className="flex gap-3"><button disabled={busy} className={button} onClick={() => void act(() => request(`/consent/requests/${r.id}/decision`, { method: "POST", body: JSON.stringify({ decision: "approve", document_ids: recordSelections[r.id]?.length ? recordSelections[r.id] : null }) }), "Access approved.")}>Approve</button>
              <button disabled={busy} className="rounded-lg border px-4 py-2 text-sm" onClick={() => void act(() => request(`/consent/requests/${r.id}/decision`, { method: "POST", body: JSON.stringify({ decision: "deny" }) }), "Access denied.")}>Deny</button></div>
          </>}
        </article>)}
      </div>
      <div className="space-y-3"><h3 className="font-semibold">Consent grants</h3>{!grants.length && <p className="text-sm text-slate-500">No consent grants.</p>}{grants.map(g => <article key={g.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-white p-5"><div><p className="font-semibold">{g.doctor_name}</p><p className="text-sm text-slate-600">{g.scope.replaceAll("_", " ")} · {g.document_ids ? `${g.document_ids.length} selected records` : "Category access"} · {g.active ? "Active" : g.is_revoked ? "Revoked" : "Expired"} · Expires {new Date(g.valid_until + (g.valid_until.endsWith("Z") ? "" : "Z")).toLocaleString()}</p></div>{g.active && <button className="rounded-lg border border-red-200 px-4 py-2 text-sm text-red-700" disabled={busy} onClick={() => void act(() => request(`/consent/grants/${g.id}/revoke`, { method: "POST" }), "Future access has been revoked.")}>Revoke</button>}</article>)}</div>
    </>}

    {user.role === "doctor" && (user.doctor?.verification_status !== "verified" ? <div className="rounded-xl border border-amber-200 bg-amber-50 p-6"><h3 className="font-semibold">Professional verification required</h3><p className="mt-2 text-sm">Current status: {user.doctor?.verification_status || "pending"}. An administrator must review your professional evidence before you can request or access patient information.</p></div> : <>
      <form className="grid gap-4 rounded-xl border bg-white p-5 md:grid-cols-2" onSubmit={sendRequest}>
        <h3 className="font-semibold md:col-span-2">Request patient access</h3>
        <label className="space-y-1 text-sm">Patient ID<input required minLength={4} maxLength={4} pattern="[A-Za-z][0-9]{3}" autoComplete="off" spellCheck={false} placeholder="e.g. A123" aria-label="Patient ID" aria-describedby="patient-id-help" value={patientId} onChange={e => setPatientId(e.target.value.toUpperCase())} className={field} /><span id="patient-id-help" className="block text-xs text-slate-500">Example: A123 — one letter followed by three digits. Find this ID on the patient&apos;s dashboard.</span></label>
        <label className="space-y-1 text-sm">Purpose<input required minLength={5} maxLength={255} value={purpose} onChange={e => setPurpose(e.target.value)} className={field} /></label>
        <label className="space-y-1 text-sm">Record scope<select value={scope} onChange={e => setScope(e.target.value)} className={field}><option value="all">All document categories</option><option value="prescriptions_only">Prescriptions</option><option value="labs_only">Lab reports</option></select></label>
        <label className="space-y-1 text-sm">Duration in hours<input required type="number" min={1} max={720} value={hours} onChange={e => setHours(Number(e.target.value))} className={field} /></label>
        <label className="flex gap-2 text-sm"><input type="checkbox" checked={upload} onChange={e => setUpload(e.target.checked)} />Also request permission to upload documents</label>
        <button disabled={busy} className={button}>Send access request</button>
      </form>
      <div className="rounded-xl border bg-white p-5"><h3 className="mb-3 font-semibold">Authorized patients</h3><label className="text-sm">Select a patient<select className={field} value={selected} onChange={e => { const id = e.target.value; setSelected(id); setDocuments([]); if (id) void act(async () => setDocuments(await api.documents.list(undefined, id)), "Authorized records loaded."); }}><option value="">Select patient</option>{patients.map(p => <option key={p.id} value={p.id}>{p.full_name}</option>)}</select></label>{!patients.length && <p className="mt-3 text-sm text-slate-500">No active patient grants.</p>}</div>
      {selected && <div className="grid gap-4 md:grid-cols-2">{documents.map(d => <DocumentCard key={d.id} document={d} />)}{!documents.length && <p className="text-sm text-slate-500">No documents available within the approved scope.</p>}</div>}
      {selected && !!patients.find(p => p.id === selected)?.upload_types.length && <><button className={button} onClick={() => setUploadOpen(true)}>Upload for selected patient</button><DocumentUploadModal isOpen={uploadOpen} onClose={() => setUploadOpen(false)} patientId={selected} allowedTypes={patients.find(p => p.id === selected)?.upload_types} onUploadSuccess={doc => setDocuments(prev => [doc, ...prev])} /></>}
      <div className="rounded-xl border bg-white p-5"><h3 className="font-semibold">Your requests</h3>{!requests.length && <p className="mt-2 text-sm text-slate-500">No requests submitted.</p>}{requests.map(r => <p className="mt-3 text-sm" key={r.id}>{r.purpose} · {r.scope.replaceAll("_", " ")} · {r.status}</p>)}</div>
    </>)}

    {user.role === "admin" && <div className="space-y-3"><h3 className="font-semibold">Professional verification queue</h3>{!doctors.length && <p className="text-sm text-slate-500">No doctors registered.</p>}{doctors.map(d => <article className="space-y-3 rounded-xl border bg-white p-5" key={d.id}><p className="font-semibold">{d.full_name} · {d.verification_status}</p><p className="text-sm">{d.license_number} · {d.specialization}</p><label className="block text-sm">Evidence reference<input minLength={5} maxLength={500} value={evidence[d.id] || ""} onChange={e => setEvidence(prev => ({ ...prev, [d.id]: e.target.value }))} placeholder="Reference to reviewed professional verification evidence" className={field} /></label><div className="flex gap-3">{["verified", "rejected", "pending"].map(status => <button key={status} disabled={busy || (evidence[d.id] || "").length < 5} className={button} onClick={() => void act(() => request(`/admin/doctors/${d.id}/verification`, { method: "POST", body: JSON.stringify({ status, evidence_reference: evidence[d.id] }) }), "Verification decision recorded.")}>{status === "verified" ? "Verify" : status === "rejected" ? "Reject" : "Reset to pending"}</button>)}</div></article>)}</div>}

    {(user.role === "patient" || user.role === "admin") && <div className="overflow-x-auto rounded-xl border bg-white p-5"><h3 className="mb-3 font-semibold">{user.role === "patient" ? "Record access history" : "Operational audit events"}</h3>{!audit.length ? <p className="text-sm text-slate-500">No events recorded.</p> : <table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="py-2">Date</th><th>Action</th>{user.role === "patient" && <th>Actor</th>}<th>Resource</th></tr></thead><tbody>{audit.map(e => <tr key={e.id} className="border-b last:border-0"><td className="py-2">{formatDate(e.created_at)}</td><td>{e.action.replaceAll("_", " ")}</td>{user.role === "patient" && <td>{e.actor_name || "System"}</td>}<td>{e.resource_type.replaceAll("_", " ")}</td></tr>)}</tbody></table>}</div>}
  </section>;
}
