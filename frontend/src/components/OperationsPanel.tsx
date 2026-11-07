"use client";
import { useDetailNavigation } from "@/lib/useDetailNavigation";

import { useLanguage } from "@/components/LanguageProvider";

import { useId, useState } from "react";
import { request } from "@/lib/api";
type Org = { id: string; name: string; status: string; version: number; evidence: string };
type Person = { id: string; name: string; email: string; role: string; active: boolean };
type Member = { user_id: string; name: string; role: string; status: string; version: number };
type Privacy = {
  id: string;
  kind: string;
  status: string;
  version: number;
  decision_reference: string | null;
};
const button = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50";
const field = "mt-1 w-full min-w-0 rounded border border-slate-300 bg-white p-2 text-sm";
function download(value: unknown, name: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function OperationsPanel() {
  const { t } = useLanguage();
  const formId = useId();
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [orgOffset, setOrgOffset] = useState(0);
  const [orgMore, setOrgMore] = useState(false);
  const [users, setUsers] = useState<Person[]>([]);
  const [userMore, setUserMore] = useState(false);
  const [selected, setSelected] = useState<Org | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [memberMore, setMemberMore] = useState(false);
  const [history, setHistory] = useState<unknown[] | null>(null);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [name, setName] = useState("");
  const [status, setStatus] = useState("pending");
  const [evidence, setEvidence] = useState("");
  const [memberUser, setMemberUser] = useState("");
  const [memberRole, setMemberRole] = useState("staff");
  const [memberStatus, setMemberStatus] = useState("active");
  const [privacy, setPrivacy] = useState<Privacy[]>([]);
  const [privacyOffset, setPrivacyOffset] = useState(0);
  const [metrics, setMetrics] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const detailNavigation = useDetailNavigation({ selected, history });
  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  }
  async function load(start = 0) {
    const [o, u, p, m] = await Promise.all([
      request<Org[]>(`/admin/organizations?limit=50&offset=${start}`),
      request<Person[]>("/admin/users?limit=50"),
      request<Privacy[]>("/admin/privacy-requests?limit=20"),
      request("/admin/metrics"),
    ]);
    setOrgs(o);
    setOrgOffset(start);
    setOrgMore(o.length === 50);
    setUsers(u);
    setUserMore(u.length === 50);
    setPrivacy(p);
    setPrivacyOffset(0);
    setMetrics(m);
  }
  function choose(org: Org | null) {
    setSelected(org);
    setName(org?.name || "");
    setStatus(org?.status || "pending");
    setEvidence("");
    setMembers([]);
    setHistory(null);
    setMemberUser("");
    if (org)
      void act(async () => {
        const rows = await request<Member[]>(`/admin/organizations/${org.id}/members?limit=50`);
        setMembers(rows);
        setMemberMore(rows.length === 50);
      });
  }
  function getHistory(start: number) {
    if (selected)
      void act(async () => {
        setHistory(
          await request<unknown[]>(`/admin/organizations/${selected.id}/history?limit=50&offset=${start}`),
        );
        setHistoryOffset(start);
      });
  }
  return (
    <section
      aria-label={t("Organization and user operations")}
      ref={detailNavigation}
      className="min-w-0 space-y-4 rounded-2xl border bg-white p-5"
    >
      <h2 className="text-lg font-semibold">{t("Organization, account & privacy operations")}</h2>
      <p className="text-sm text-slate-600">
        {t(
          "Organization membership never grants clinical access. Organization-bound consent requires verified membership on every request. Patient-approved personal grants remain separate. Administrator accounts are managed through the provisioning CLI.",
        )}
      </p>
      {error && (
        <p role="alert" className="break-words text-red-700">
          {t(error)}
        </p>
      )}
      {message && (
        <p role="status" className="text-emerald-800">
          {t(message)}
        </p>
      )}
      <button type="button" className={button} disabled={busy} onClick={() => void act(() => load())}>
        {t("Refresh operational records")}
      </button>
      {metrics !== null && (
        <details>
          <summary className="cursor-pointer font-semibold">
            {t("Live aggregate operational metrics")}
          </summary>
          <pre className="overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(metrics, null, 2)}</pre>
        </details>
      )}
      <section className="space-y-3 rounded-xl border p-4">
        <h3 className="font-semibold">{t("Organizations")}</h3>
        <button type="button" className={button} disabled={busy} onClick={() => choose(null)}>
          {t("New organization")}
        </button>
        {orgs.map((org) => (
          <button
            type="button"
            key={org.id}
            className={`${button} block w-full break-words text-left`}
            disabled={busy}
            onClick={() => choose(org)}
          >
            {org.name} · {org.status} {t("· Version")} {org.version}
          </button>
        ))}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className={button}
            disabled={busy || orgOffset === 0}
            onClick={() => void act(() => load(Math.max(0, orgOffset - 50)))}
          >
            {t("Previous organizations")}
          </button>
          <button
            type="button"
            className={button}
            disabled={busy || !orgMore}
            onClick={() => void act(() => load(orgOffset + 50))}
          >
            {t("More organizations")}
          </button>
        </div>
        <form
          aria-label={t("Organization editor")}
          data-detail-target="selected"
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void act(async () => {
              const org = await request<Org>(`/admin/organizations${selected ? `/${selected.id}` : ""}`, {
                method: selected ? "PUT" : "POST",
                body: JSON.stringify({ name, status, evidence, expected_version: selected?.version || 0 }),
              });
              await load(orgOffset);
              setSelected(org);
              setMessage("Organization status saved with evidence history.");
            });
          }}
        >
          <label className="block text-sm">
            {t("Organization name")}
            <input
              className={field}
              required
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="block text-sm" htmlFor={`${formId}-org-status`}>
            {t("Organization verification status")}
          </label>
          <select
            id={`${formId}-org-status`}
            className={field}
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="pending">{t("Pending")}</option>
            <option value="verified">{t("Verified after evidence review")}</option>
            <option value="inactive">{t("Inactive")}</option>
          </select>
          <label className="block text-sm">
            {t("Operational evidence reference")}
            <input
              className={field}
              required
              minLength={5}
              maxLength={500}
              value={evidence}
              onChange={(event) => setEvidence(event.target.value)}
            />
          </label>
          <button type="submit" className={button} disabled={busy}>
            {t("Save organization")}
          </button>
        </form>
        {selected && (
          <>
            <h4 className="font-semibold">
              {t("Members of")} {selected.name}
            </h4>
            {members.map((member) => (
              <button
                type="button"
                key={member.user_id}
                className={`${button} block w-full text-left`}
                onClick={() => {
                  setMemberUser(member.user_id);
                  setMemberRole(member.role);
                  setMemberStatus(member.status);
                }}
              >
                {member.name} · {member.role} · {member.status} {t("· Version")} {member.version}
              </button>
            ))}
            {memberMore && (
              <button
                type="button"
                className={button}
                disabled={busy}
                onClick={() =>
                  void act(async () => {
                    const rows = await request<Member[]>(
                      `/admin/organizations/${selected.id}/members?limit=50&offset=${members.length}`,
                    );
                    setMembers((previous) => [...previous, ...rows]);
                    setMemberMore(rows.length === 50);
                  })
                }
              >
                {t("More organization members")}
              </button>
            )}
            <form
              aria-label={t("Organization membership editor")}
              className="space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                void act(async () => {
                  await request(`/admin/organizations/${selected.id}/members`, {
                    method: "PUT",
                    body: JSON.stringify({
                      user_id: memberUser,
                      role: memberRole,
                      status: memberStatus,
                      expected_version: members.find((member) => member.user_id === memberUser)?.version || 0,
                      evidence,
                    }),
                  });
                  const rows = await request<Member[]>(
                    `/admin/organizations/${selected.id}/members?limit=50`,
                  );
                  setMembers(rows);
                  setMemberMore(rows.length === 50);
                  setMessage(
                    "Organization membership saved. Clinical access still requires patient consent.",
                  );
                });
              }}
            >
              <label className="block text-sm" htmlFor={`${formId}-member-user`}>
                {t("Membership account")}
              </label>
              <select
                id={`${formId}-member-user`}
                className={field}
                required
                value={memberUser}
                onChange={(event) => {
                  setMemberUser(event.target.value);
                  const member = members.find((row) => row.user_id === event.target.value);
                  setMemberRole(member?.role || "staff");
                  setMemberStatus(member?.status || "active");
                }}
              >
                <option value="">{t("Select an account")}</option>
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.name} · {t(user.role)}
                  </option>
                ))}
              </select>
              <label className="block text-sm" htmlFor={`${formId}-member-role`}>
                {t("Organization role")}
              </label>
              <select
                id={`${formId}-member-role`}
                className={field}
                value={memberRole}
                onChange={(event) => setMemberRole(event.target.value)}
              >
                <option value="staff">{t("Operational staff (no clinical access)")}</option>
                <option value="clinician">{t("Verified clinician")}</option>
              </select>
              <label className="block text-sm" htmlFor={`${formId}-member-status`}>
                {t("Membership status")}
              </label>
              <select
                id={`${formId}-member-status`}
                className={field}
                value={memberStatus}
                onChange={(event) => setMemberStatus(event.target.value)}
              >
                <option value="active">{t("Active")}</option>
                <option value="inactive">{t("Inactive")}</option>
              </select>
              <p className="text-xs">
                {t(
                  "Uses the operational evidence reference above. Load additional accounts/members before editing an existing membership.",
                )}
              </p>
              <button type="submit" className={button} disabled={busy || evidence.trim().length < 5}>
                {t("Save organization membership")}
              </button>
            </form>
            <button type="button" className={button} disabled={busy} onClick={() => getHistory(0)}>
              {t("View organization evidence history")}
            </button>
            {history && (
              <>
                <pre
                  data-detail-target="history"
                  className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs"
                >
                  {JSON.stringify(history, null, 2)}
                </pre>
                <button
                  type="button"
                  className={button}
                  disabled={busy || historyOffset === 0}
                  onClick={() => getHistory(Math.max(0, historyOffset - 50))}
                >
                  {t("Previous organization history")}
                </button>
                <button
                  type="button"
                  className={button}
                  disabled={busy || history.length < 50}
                  onClick={() => getHistory(historyOffset + 50)}
                >
                  {t("Older organization history")}
                </button>
              </>
            )}
          </>
        )}
      </section>
      <details className="space-y-3 rounded-xl border p-4">
        <summary className="cursor-pointer font-semibold">{t("Account lifecycle")}</summary>
        <p className="text-sm">
          {t(
            "Deactivation revokes current sessions. Reactivation requires a new login. Roles and clinical profiles are preserved.",
          )}
        </p>
        {users.map((user) => (
          <article
            className="flex flex-wrap items-center justify-between gap-2 rounded border p-3 text-sm"
            key={user.id}
          >
            <p className="break-words">
              {user.name} · {user.email} · {t(user.role)} · {user.active ? t("Active") : t("Inactive")}
            </p>
            {user.role !== "admin" && (
              <button
                type="button"
                className={button}
                disabled={busy || evidence.trim().length < 5}
                onClick={() =>
                  void act(async () => {
                    await request(`/admin/users/${user.id}/activation`, {
                      method: "PUT",
                      body: JSON.stringify({ expected_active: user.active, active: !user.active, evidence }),
                    });
                    setUsers((previous) =>
                      previous.map((row) => (row.id === user.id ? { ...row, active: !user.active } : row)),
                    );
                    setMessage(
                      "Account activation updated; deactivated accounts had their sessions revoked.",
                    );
                  })
                }
              >
                {user.active ? t("Deactivate") : t("Reactivate")} {user.name}
              </button>
            )}
          </article>
        ))}
        {userMore && (
          <button
            type="button"
            className={button}
            disabled={busy}
            onClick={() =>
              void act(async () => {
                const rows = await request<Person[]>(`/admin/users?limit=50&offset=${users.length}`);
                setUsers((previous) => [...previous, ...rows]);
                setUserMore(rows.length === 50);
              })
            }
          >
            {t("Load more accounts")}
          </button>
        )}
        <p className="text-xs">
          {t(
            "Enter an operational evidence reference in the organization form before changing account activation.",
          )}
        </p>
      </details>
      <details className="space-y-3 rounded-xl border p-4">
        <summary className="cursor-pointer font-semibold">{t("Privacy request review queue")}</summary>
        <p className="text-sm">
          {t(
            "These are administrative requests. Closing a request does not erase data. Erasure needs an approved retention policy, source/object handling and an execution review.",
          )}
        </p>
        {privacy.map((row) => (
          <article key={row.id} className="space-y-2 rounded border p-3 text-sm">
            <p>
              {row.kind} · {row.status} {t("· Version")} {row.version}
            </p>
            <p>{row.decision_reference}</p>
            {row.status !== "closed" &&
              ["under_review", "closed"].map((next) => (
                <button
                  type="button"
                  className={button}
                  key={next}
                  disabled={busy || evidence.trim().length < 5}
                  onClick={() =>
                    void act(async () => {
                      const updated = await request<Privacy>(`/admin/privacy-requests/${row.id}`, {
                        method: "PUT",
                        body: JSON.stringify({
                          expected_version: row.version,
                          status: next,
                          decision_reference: evidence,
                        }),
                      });
                      setPrivacy((previous) => previous.map((item) => (item.id === row.id ? updated : item)));
                      setMessage("Privacy request review status saved. No medical records were erased.");
                    })
                  }
                >
                  {t("Mark")} {next.replaceAll("_", " ")}
                </button>
              ))}
          </article>
        ))}
        <button
          type="button"
          className={button}
          disabled={busy || privacyOffset === 0}
          onClick={() =>
            void act(async () => {
              const start = Math.max(0, privacyOffset - 20);
              setPrivacy(await request<Privacy[]>(`/admin/privacy-requests?limit=20&offset=${start}`));
              setPrivacyOffset(start);
            })
          }
        >
          {t("Previous privacy requests")}
        </button>
        <button
          type="button"
          className={button}
          disabled={busy || privacy.length < 20}
          onClick={() =>
            void act(async () => {
              setPrivacy(
                await request<Privacy[]>(`/admin/privacy-requests?limit=20&offset=${privacyOffset + 20}`),
              );
              setPrivacyOffset((value) => value + 20);
            })
          }
        >
          {t("Older privacy requests")}
        </button>
      </details>
    </section>
  );
}

export function PrivacyPanel() {
  const { t } = useLanguage();
  const [kind, setKind] = useState("export");
  const [rows, setRows] = useState<Privacy[] | null>(null);
  const [offset, setOffset] = useState(0);
  const [exportOffset, setExportOffset] = useState(0);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Privacy request failed");
    } finally {
      setBusy(false);
    }
  }
  function load(start = 0) {
    void act(async () => {
      setRows(await request<Privacy[]>(`/privacy/requests?limit=20&offset=${start}`));
      setOffset(start);
    });
  }
  function exportPage(start: number) {
    void act(async () => {
      const result = await request<{ has_more: boolean }>(`/privacy/export?limit=20&offset=${start}`);
      download(result, `caregap-personal-records-${start}.json`);
      setMore(result.has_more);
      setExportOffset(start);
      setMessage(
        "Personal record page downloaded. Original document files have separate authenticated download controls.",
      );
    });
  }
  return (
    <details
      aria-label={t("Privacy and data requests")}
      className="space-y-3 rounded-2xl border bg-white p-5"
    >
      <summary className="cursor-pointer font-semibold">{t("Privacy & personal data requests")}</summary>
      <p className="text-sm">
        {t(
          "Download paged account/record extracts or request administrative review. Existing record correction controls retain earlier versions. An erasure request does not immediately delete your records; retention and shared-source obligations need review.",
        )}
      </p>
      {error && (
        <p role="alert" className="text-red-700">
          {t(error)}
        </p>
      )}
      {message && (
        <p role="status" className="text-emerald-800">
          {t(message)}
        </p>
      )}
      <button type="button" className={button} disabled={busy} onClick={() => exportPage(0)}>
        {t("Download personal record extract")}
      </button>
      {more && (
        <button
          type="button"
          className={button}
          disabled={busy}
          onClick={() => exportPage(exportOffset + 20)}
        >
          {t("Download next personal record page")}
        </button>
      )}
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          void act(async () => {
            await request("/privacy/requests", { method: "POST", body: JSON.stringify({ kind }) });
            setRows(await request<Privacy[]>("/privacy/requests?limit=20"));
            setOffset(0);
            setMessage("Privacy review request submitted. No records were erased.");
          });
        }}
      >
        <label className="block text-sm">
          {t("Privacy request type")}
          <select className={field} value={kind} onChange={(event) => setKind(event.target.value)}>
            <option value="export">{t("Export assistance")}</option>
            <option value="correction">{t("Correction review")}</option>
            <option value="erasure">{t("Erasure / retention review")}</option>
          </select>
        </label>
        <button type="submit" className={button} disabled={busy}>
          {t("Submit privacy review request")}
        </button>
      </form>
      <button type="button" className={button} disabled={busy} onClick={() => load()}>
        {t("View my privacy requests")}
      </button>
      {rows && (
        <>
          {rows.map((row) => (
            <article key={row.id} className="rounded border p-3 text-sm">
              <p>
                {row.kind} · {row.status} {t("· Version")} {row.version}
              </p>
              <p>{row.decision_reference || t("Awaiting administrative review")}</p>
            </article>
          ))}
          <button
            type="button"
            className={button}
            disabled={busy || offset === 0}
            onClick={() => load(Math.max(0, offset - 20))}
          >
            {t("Previous privacy requests")}
          </button>
          <button
            type="button"
            className={button}
            disabled={busy || rows.length < 20}
            onClick={() => load(offset + 20)}
          >
            {t("Older privacy requests")}
          </button>
        </>
      )}
    </details>
  );
}
