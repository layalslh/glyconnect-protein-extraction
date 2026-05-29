import requests
import json
import time
import os
import csv

# =============================================================================
# GlycoShape Re-Glyco API — Batch Script
# Pipeline per protein:
#   1. Create session  → session_uuid
#   2. Launch scan job → job_uuid
#   3. Poll until completed
#   4. Download all.pdb (with size check)
#   5. Write row to CSV + append to log files
# Outputs: batch_report.json, batch_report.csv, succes.txt,
#          erreurs.txt, proteins_failed.txt
# =============================================================================

BASE        = "https://glycoshape.org"
SAVE_FOLDER = "batch_results"
os.makedirs(SAVE_FOLDER, exist_ok=True)

PROTEINS_IGNORE = {
    "O14639", "A3KN83", "E1BNC9", "F1SFZ8",
    "O00268", "O08537", "O14920", "O60641",
    "O75376", "P00915", "P01106", "P01833",
    "P02470", "P02488", "P02505", "P02510",
    "P02511", "P02545-3", "P02549", "P02730",
    "P03070", "P03372", "P04040", "P05783",
    "P05787", "P08047", "P08318", "P08670",
    "P10636", "P11166", "P11171", "P11277",
    "P11818", "P11831", "P12270", "P12839",
    "P13646", "P15822", "P16157", "P16452",
    "P17599", "P17955", "P18146", "P18583-1",
    "P19527", "P19785", "P21138", "P24623",
    "P25311", "P35658", "P37198", "P37840",
    "P49790", "P49792", "P49884", "P51610",
    "P52948-4", "P54939", "P68431", "P68871",
    "P69905", "P78417", "Q04637", "Q09666",
    "Q12778", "Q12830", "Q14157", "Q14684",
    "Q14814", "Q14980", "Q2KHR3", "Q4Q843",
    "Q5VT52", "Q6MZP7", "Q6P4R8", "Q6PJT7-2",
    "Q70E73", "Q7Z3J3", "Q7Z3K3-2", "Q7Z589",
    "Q7Z739", "Q8IWI9", "Q8N3V7", "Q8NDX5",
    "Q8WWM7", "Q8WXI9", "Q96HA1", "Q96KR1",
    "Q96KX2", "Q96PK6", "Q96Q06", "Q96T58",
    "Q99808", "Q9BYJ9", "Q9H4A3", "Q9HAU0",
    "Q9NR12-4", "Q9NXV6", "Q9NYV4", "Q9P2N5",
    "Q9P2N6", "Q9UKD1", "Q9UKY1", "Q9UQ35",
    "Q9Y2X9", "Q9Y520",
}

with open("data/proteins.txt") as f: # Chemin vers la liste des protéines
    PROTEINS = [line.strip() for line in f if line.strip()]

PROTEINS = [p for p in PROTEINS if p not in PROTEINS_IGNORE]

print(f"Protéines après exclusion : {len(PROTEINS)} (ignoré {44 - (800 - len(PROTEINS))} de la blacklist)")
print(f"Loaded {len(PROTEINS)} proteins")

# =============================================================================
# Pipeline functions
# Each wraps network errors as Exception("PREFIX: ...") so the main loop
# can classify them with a clean startswith() check.
# =============================================================================

def creer_session(uniprot_id):
    try:
        r = requests.post(f"{BASE}/api/sessions", json={"protID": uniprot_id}, timeout=30)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise Exception(f"API_ERROR: {e}")
    donnees      = r.json()
    session_uuid = donnees.get("session_uuid")
    if not session_uuid:
        raise Exception("SESSION_ERROR: No session UUID returned — protein may not exist in AlphaFold")
    return session_uuid


def soumettre_job(session_uuid):
    try:
        r = requests.post(f"{BASE}/api/jobs", json={
            "session_uuid": session_uuid,
            "jobType":      "scan",
        }, timeout=30)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise Exception(f"API_ERROR: {e}")
    job      = r.json()
    job_uuid = job.get("uuid") or job.get("job_uuid") or job.get("id")
    if not job_uuid:
        raise Exception("API_ERROR: No job UUID returned")
    return job_uuid


def attendre_job(job_uuid, max_wait=300):
    waited = 0
    while waited < max_wait:
        try:
            r = requests.get(f"{BASE}/api/jobs/{job_uuid}", timeout=30)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API_ERROR: {e}")
        job_status = r.json().get("status")
        print(f"   Status: {job_status}")
        if job_status == "completed":
            return
        if job_status == "failed":
            raise Exception("JOB_FAILED: Server-side job failure")
        time.sleep(5)
        waited += 5
    raise Exception("TIMEOUT: Job took more than 5 minutes — server may be overloaded")


def telecharger_pdb(job_uuid, pdb_path):
    try:
        r = requests.get(f"{BASE}/api/jobs/{job_uuid}/files", timeout=30)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise Exception(f"API_ERROR: {e}")
    file_names = [f["name"] for f in r.json().get("files", [])]
    print(f"   Files: {file_names}")
    if "all.pdb" not in file_names:
        raise Exception("NO_PDB: Scan completed but no all.pdb was generated")
    try:
        r = requests.get(f"{BASE}/api/jobs/{job_uuid}/files/all.pdb", timeout=60)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise Exception(f"API_ERROR: {e}")
    if len(r.content) < 100:
        raise Exception("NO_PDB: PDB file is empty or too small")
    with open(pdb_path, "wb") as f:
        f.write(r.content)
    return len(r.content)


def classifier_erreur(msg):
    for prefix in ("JOB_FAILED", "TIMEOUT", "NO_PDB", "SESSION_ERROR", "API_ERROR"):
        if msg.startswith(prefix):
            return prefix
    return "UNKNOWN_ERROR"


# =============================================================================
# Output file paths
# =============================================================================
json_path    = os.path.join(SAVE_FOLDER, "batch_report.json")
csv_path     = os.path.join(SAVE_FOLDER, "batch_report.csv")
succes_path  = os.path.join(SAVE_FOLDER, "succes.txt")
erreurs_path = os.path.join(SAVE_FOLDER, "erreurs.txt")
failed_path  = os.path.join(SAVE_FOLDER, "proteins_failed.txt")

summary  = []
csv_file = open(csv_path, "w", newline="", encoding="utf-8")
writer   = csv.DictWriter(csv_file, fieldnames=[
    "uniprot_id", "statut", "pdb_saved", "error_type", "error_message"
])
writer.writeheader()

# =============================================================================
# MAIN LOOP
# =============================================================================
try:
    for uniprot_id in PROTEINS:
        print(f"\n{'='*60}")
        print(f"Processing: {uniprot_id}")
        print(f"{'='*60}")

        protein_result = {
            "protein_id":    uniprot_id,
            "status":        None,
            "error_type":    None,
            "error_message": None,
            "pdb_saved":     False,
        }

        pdb_path = os.path.join(SAVE_FOLDER,f"{uniprot_id}.pdb")

        # ---------------------------------------------------------------------
        # Skip if output already exists
        # ---------------------------------------------------------------------
        if os.path.exists(pdb_path):
            print(f"[{uniprot_id}] Already exists — logging metadata only")
            pdb_kb = os.path.getsize(pdb_path) // 1024
            protein_result["status"]    = "ALREADY_DONE"
            protein_result["pdb_saved"] = True

            with open(succes_path, "a") as f:
                f.write(f"{uniprot_id} | {pdb_kb} KB\n")

            summary.append(protein_result)
            writer.writerow({
                "uniprot_id":    uniprot_id,
                "statut":        "ALREADY_DONE",
                "pdb_saved":     True,
                "error_type":    "",
                "error_message": "",
            })
            csv_file.flush()
            continue

        try:
            # Step 1 — Create session
            print(f"[{uniprot_id}] Step 1: Creating session...")
            session_uuid = creer_session(uniprot_id)
            print(f"[{uniprot_id}] Session UUID: {session_uuid}")

            # Step 2 — Launch scan job
            print(f"[{uniprot_id}] Step 2: Launching scan job...")
            job_uuid = soumettre_job(session_uuid)
            print(f"[{uniprot_id}] Job UUID: {job_uuid}")

            # Step 3 — Poll until complete
            print(f"[{uniprot_id}] Step 3: Waiting for job...")
            attendre_job(job_uuid)

            # Step 4 — Download PDB
            print(f"[{uniprot_id}] Step 4: Downloading all.pdb...")
            pdb_bytes = telecharger_pdb(job_uuid, pdb_path)
            pdb_kb    = pdb_bytes // 1024
            print(f"[{uniprot_id}] PDB saved: {pdb_path} ({pdb_kb} KB)")

            protein_result["pdb_saved"] = True
            protein_result["status"]    = "SUCCESS"

            with open(succes_path, "a") as f:
                f.write(f"{uniprot_id} | {pdb_kb} KB\n")

            time.sleep(2)

        except Exception as e:
            error_msg  = str(e)
            error_type = classifier_erreur(error_msg)

            protein_result["status"]        = "ERROR"
            protein_result["error_type"]    = error_type
            protein_result["error_message"] = error_msg

            print(f"\n[{uniprot_id}] *** ERROR ***")
            print(f"[{uniprot_id}] Type:    {error_type}")
            print(f"[{uniprot_id}] Message: {error_msg}")

            with open(erreurs_path, "a") as f:
                f.write(f"{uniprot_id} | {error_type} | {error_msg}\n")

        writer.writerow({
            "uniprot_id":    uniprot_id,
            "statut":        protein_result["status"],
            "pdb_saved":     protein_result["pdb_saved"],
            "error_type":    protein_result["error_type"]    or "",
            "error_message": protein_result["error_message"] or "",
        })
        csv_file.flush()
        summary.append(protein_result)

except KeyboardInterrupt:
    print("\n\nStopped by user (Ctrl+C). Saving partial report...")

finally:
    csv_file.close()

# =============================================================================
# Save JSON report and retry list (always runs, even after Ctrl+C)
# =============================================================================
with open(json_path, "w") as f:
    json.dump(summary, f, indent=2)

failed = [r["protein_id"] for r in summary if r["status"] == "ERROR"]
with open(failed_path, "w") as f:
    for pid in failed:
        f.write(f"{pid}\n")

# =============================================================================
# Final summary table
# =============================================================================
print(f"\n{'='*60}")
print("BATCH COMPLETE — SUMMARY")
print(f"{'='*60}")
print(f"{'Protein':<12} {'Status':<14} {'PDB':<6} {'Error'}")
print("-" * 60)
for entry in summary:
    pdb   = "✓" if entry["pdb_saved"] else "✗"
    error = entry["error_type"] or ""
    print(f"{entry['protein_id']:<12} {entry['status']:<14} {pdb:<6} {error}")

successes    = sum(1 for r in summary if r["status"] == "SUCCESS")
already_done = sum(1 for r in summary if r["status"] == "ALREADY_DONE")
errors       = len(failed)
print(f"\nSuccess: {successes}  |  Already done: {already_done}  |  Errors: {errors}")
print(f"\nJSON report:      {json_path}")
print(f"CSV report:       {csv_path}")
print(f"Failed proteins:  {failed_path} ({errors} proteins)")
print(f"All files in:     {SAVE_FOLDER}")
