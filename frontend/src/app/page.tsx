import Link from "next/link";
import { ArrowRight, FileText, ShieldCheck, History, LockKeyhole, ClipboardCheck, Stethoscope } from "lucide-react";
import { Navbar } from "@/components/Navbar";

export default function HomePage() {
  return <div className="min-h-screen bg-slate-50">
    <Navbar />
    <main>
      <section className="border-b bg-white">
        <div className="mx-auto grid max-w-7xl gap-12 px-6 py-20 lg:grid-cols-2 lg:items-center lg:py-28">
          <div>
            <p className="mb-5 inline-flex items-center gap-2 rounded-full bg-blue-50 px-4 py-2 text-xs font-semibold text-blue-700"><ShieldCheck size={16} />Your records. Your permission.</p>
            <h1 className="text-4xl font-extrabold leading-tight tracking-tight text-slate-900 sm:text-5xl">A clearer picture of your care, <span className="text-blue-600">in one place.</span></h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-600">Keep prescriptions, reports, and medical documents together. Choose which records a verified clinician can access, for how long, and review the access history.</p>
            <div className="mt-8 flex flex-wrap gap-3"><Link href="/register" className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white hover:bg-blue-700">Create your account <ArrowRight size={18} /></Link><Link href="/login" className="inline-flex items-center gap-2 rounded-xl border px-6 py-3 font-semibold text-slate-700 hover:bg-slate-50"><Stethoscope size={18} />Clinician sign in</Link></div>
            <p className="mt-5 text-xs text-slate-500">Development release · Use synthetic records only</p>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6 shadow-lg sm:p-8">
            <div className="mb-6 flex items-center justify-between"><h2 className="font-bold text-slate-800">Your care, connected</h2><span className="rounded-full bg-white px-3 py-1 text-xs text-slate-500">Workflow overview</span></div>
            {[
              { icon: FileText, title: "Preserve the source", text: "Upload an original PDF, JPG, or PNG. Clinical contents remain unverified until reviewed." },
              { icon: ClipboardCheck, title: "Review the request", text: "See the clinician, purpose, record scope, duration, and requested upload permission." },
              { icon: LockKeyhole, title: "Stay in control", text: "Approve selected records or a document category. Revoke future access at any time." },
              { icon: History, title: "Know who accessed records", text: "Review recorded access and sharing events from your dashboard." },
            ].map(({ icon: Icon, title, text }, i) => <div key={title} className={`flex gap-4 py-5 ${i ? "border-t" : ""}`}><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-100 text-blue-700"><Icon size={20} /></div><div><h3 className="text-sm font-semibold text-slate-900">{title}</h3><p className="mt-1 text-sm leading-relaxed text-slate-500">{text}</p></div></div>)}
          </div>
        </div>
      </section>
      <section className="mx-auto max-w-7xl px-6 py-14"><h2 className="text-2xl font-bold tracking-tight">Building a foundation for care continuity</h2><p className="mt-4 max-w-3xl leading-relaxed text-slate-600">The current release focuses on patient records and consent. Prescription digitization, medication reconciliation, care-gap predictions, notifications, and FHIR exchange are planned milestones. They are not available as clinical services in this release.</p></section>
    </main>
    <footer className="border-t bg-white px-6 py-6 text-center text-xs text-slate-500">© 2026 CareGap 360 · Clinical, legal, security, and operational review required before real patient use.</footer>
  </div>;
}
