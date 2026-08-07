from src.database import (
    fetch_simple_overdue_invoices,
    fetch_contact_emails,
    fetch_contact_cc_emails,
    fetch_from_dg_emails,
    build_acctno_email_map,
)
from src.report_generator import (
    group_invoices_by_customer,
    calculate_days_overdue,
    standardize_overdue_dataframe,
)
from src.email_sender import send_overdue_statement, log_email_result, allocate_run_paths
from config.config import TEST_EMAIL, TRIAL_TARGETS, TRIAL_SAFE_TO, TRIAL_SAFE_CC
import argparse


def run_weekly_overdue_emails(mode: str = "test"):
    """
    Main function to run weekly overdue reminder emails.

    mode:
        - "dry-run"    : generate + save HTML only (no emails sent)
        - "test"       : generate + save HTML, send all to TEST_EMAIL
        - "trial-safe" : like trial, but To/CC redirected to TRIAL_SAFE_TO / TRIAL_SAFE_CC
        - "trial"      : only TRIAL_TARGETS, real customer To/CC
        - "prod"       : all customers, real customer To/CC
    """
    print("=" * 60)
    print(f"=== Starting Weekly Overdue Invoice Reminder  (mode: {mode}) ===")
    print("=" * 60)
    
    # Allocate new run folder + log file for this mode (never overwrite same-day runs)
    run_label, email_folder, log_file = allocate_run_paths(mode)
    print(f"Run label   : {run_label}")
    print(f"HTML folder : {email_folder}")
    print(f"Log file    : {log_file}")
    
    # 1. Fetch overdue invoices
    print("\n📥 Fetching overdue invoices...")
    df = fetch_simple_overdue_invoices()
    
    if df.empty:
        print("No overdue invoices found. Exiting.")
        return
    
    print(f"Found {len(df)} overdue invoice(s) before filtering.")
    
    # 2. Fetch contact emails (To: SA1x, CC: SA2–SA9) and build maps
    print("\n📥 Fetching contact emails...")
    contacts_df = fetch_contact_emails()
    email_map = build_acctno_email_map(contacts_df)
    
    print("\n📥 Fetching CC contact emails...")
    cc_contacts_df = fetch_contact_cc_emails()
    cc_map = build_acctno_email_map(cc_contacts_df)
    
    print("\n📥 Fetching From/DG emails (SA01)...")
    from_dg_df = fetch_from_dg_emails()
    from_dg_map = build_acctno_email_map(from_dg_df)
    
    # 3. Standardize + calculate Days Overdue
    df = standardize_overdue_dataframe(df)
    df = calculate_days_overdue(df)
    
    # 4. Only keep strictly overdue invoices (exclude due today)
    df = df[df['DaysOverdue'] > 0]
    
    if df.empty:
        print("No strictly overdue invoices found after filtering. Exiting.")
        return
    
    print(f"After filtering (DaysOverdue > 0): {len(df)} invoices.")
    
    # 5. Group by Customer + Company No. (1 email per company)
    groups = group_invoices_by_customer(df)
    print(f"Total email groups before trial filter: {len(groups)}")
    
    # Trial allow-list (used for trial filter AND dry-run trial stats)
    trial_allowed = set()
    if TRIAL_TARGETS:
        trial_allowed = {
            (t["customer_name"], int(t["company_no"]))
            for t in TRIAL_TARGETS
        }
    
    # 6. Trial / trial-safe: keep only selected (Customer Name + Company No.) pairs
    if mode in ("trial", "trial-safe"):
        if not trial_allowed:
            print("⚠️  TRIAL_TARGETS list is empty – nothing to send.")
            print("   Please add entries in config/config.py, e.g.:")
            print('   {"customer_name": "ABC TRADING COMPANY", "company_no": 1}')
            return
        
        groups = {
            k: v for k, v in groups.items()
            if (k[0], k[1]) in trial_allowed
        }
        
        print(f"{mode}: {len(groups)} group(s) matched from TRIAL_TARGETS")
        for t in TRIAL_TARGETS:
            print(f"  - {t['customer_name']} | Company {t['company_no']}")
        
        if mode == "trial-safe":
            safe_to = [e for e in (TRIAL_SAFE_TO or []) if e]
            safe_cc = [e for e in (TRIAL_SAFE_CC or []) if e]
            if not safe_to:
                print("⚠️  TRIAL_SAFE_TO is empty – set 1–2 internal emails in config/config.py")
                return
            print(f"trial-safe redirect → To: {safe_to} | CC: {safe_cc or '(none)'}")
        
        if not groups:
            print("No matching customer+company pairs found in overdue data. Exiting.")
            return
    
    # 7. Process each group
    success_count = 0
    fail_count = 0
    skipped_no_email = 0
    
    # Separate stats for trial-list customers (useful in dry-run of full population)
    trial_success = 0
    trial_fail = 0
    trial_skipped = 0
    trial_groups = 0
    trial_invoices = 0
    
    for (customer_name, company_no), group_df in groups.items():
        company_label = f"Company {company_no}" if company_no is not None else "Unknown Company"
        is_trial_target = (customer_name, company_no) in trial_allowed
        trial_tag = " [TRIAL]" if is_trial_target and mode == "dry-run" else ""
        
        print(f"\nProcessing: {customer_name} | {company_label} ({len(group_df)} invoices){trial_tag}")
        
        if is_trial_target:
            trial_groups += 1
            trial_invoices += len(group_df)
        
        # Resolve ACCTNO from group
        acctno = None
        if 'ACCTNO' in group_df.columns and group_df['ACCTNO'].notna().any():
            acctno = str(group_df['ACCTNO'].dropna().iloc[0]).strip()
        
        # Distinct emails for this account (Option A: all on To:)
        to_emails = email_map.get(acctno, []) if acctno else []
        
        # CC from CONTACTS SA2–SA9 (same ACCTNO)
        cc_emails = cc_map.get(acctno, []) if acctno else []
        
        if not to_emails:
            print(f"  ⚠️  No contact email for ACCTNO={acctno!r} – skipped")
            skipped_no_email += 1
            if is_trial_target:
                trial_skipped += 1
            
            invoice_count = len(group_df)
            total_amount = 0.0
            if 'COA' in group_df.columns:
                total_amount = float(group_df['COA'].sum())
            elif 'OA' in group_df.columns:
                total_amount = float(group_df['OA'].sum())
            
            log_email_result(
                customer_name=customer_name,
                recipient="",
                status="SKIPPED_NO_EMAIL",
                invoice_count=invoice_count,
                total_amount=total_amount,
                saved_file="",
                error_message=f"No To: email for ACCTNO={acctno!r}",
                cc=", ".join(cc_emails) if cc_emails else "",
                company_no=company_no,
                is_trial=is_trial_target,
                log_file=log_file,
            )
            continue
        
        # From DG (CONTACTS SA01) — one address per send
        from_list = from_dg_map.get(acctno, []) if acctno else []
        from_dg = from_list[0] if from_list else None
        
        print(f"  📬 Real To ({len(to_emails)}): {', '.join(to_emails)}")
        if cc_emails:
            print(f"  📎 Real CC from contacts ({len(cc_emails)}): {', '.join(cc_emails)}")
        print(f"  📤 From DG: {from_dg or '(missing SA01)'}")
        
        # trial-safe: keep real To/CC in logs/console, but send only to safe defaults
        send_to = to_emails
        send_cc = cc_emails
        if mode == "trial-safe":
            send_to = [e for e in (TRIAL_SAFE_TO or []) if e]
            send_cc = [e for e in (TRIAL_SAFE_CC or []) if e]
            print(f"  🔒 trial-safe override → To: {', '.join(send_to)} | CC: {', '.join(send_cc) if send_cc else '(none)'}")
        
        if mode == "dry-run":
            send_mode = "dry-run"
        elif mode == "test":
            send_mode = "test"
        else:
            send_mode = "prod"  # trial, trial-safe, prod
        
        success = send_overdue_statement(
            to_email=send_to,
            customer_name=customer_name,
            customer_df=group_df,
            mode=send_mode,
            company_no=company_no,
            extra_cc=send_cc,
            from_dg=from_dg,
            is_trial=is_trial_target,
            email_folder=email_folder,
            log_file=log_file,
        )
        
        if success:
            success_count += 1
            if is_trial_target:
                trial_success += 1
        else:
            fail_count += 1
            if is_trial_target:
                trial_fail += 1
    
    # 8. Summary
    print("\n" + "=" * 60)
    print("=== Run Summary (ALL) ===")
    print(f"Mode          : {mode}")
    print(f"Run label     : {run_label}")
    print(f"HTML folder   : {email_folder}")
    print(f"Log file      : {log_file}")
    print(f"Email groups  : {len(groups)}")
    print(f"Success       : {success_count}")
    print(f"Failed        : {fail_count}")
    print(f"Skipped (no email): {skipped_no_email}")
    print("=" * 60)
    
    # Separate trial-list stats (especially useful in dry-run of full data)
    if trial_allowed and mode == "dry-run":
        print("\n" + "=" * 60)
        print("=== Trial list only (from TRIAL_TARGETS) ===")
        print(f"Configured targets : {len(trial_allowed)}")
        print(f"Matched groups     : {trial_groups}")
        print(f"Matched invoices   : {trial_invoices}")
        print(f"Would send (OK)    : {trial_success}")
        print(f"Would fail         : {trial_fail}")
        print(f"Skipped (no email) : {trial_skipped}")
        if TRIAL_TARGETS:
            print("Targets:")
            for t in TRIAL_TARGETS:
                key = (t["customer_name"], int(t["company_no"]))
                matched = "matched" if key in {(k[0], k[1]) for k in groups.keys()} or trial_groups else "not in overdue set"
                # simpler: show configured list
                print(f"  - {t['customer_name']} | Company {t['company_no']}")
        print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send weekly overdue invoice reminders")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["dry-run", "test", "trial-safe", "trial", "prod"],
        default="test",
        help="Run mode: dry-run | test | trial-safe | trial | prod"
    )
    
    args = parser.parse_args()
    
    run_weekly_overdue_emails(mode=args.mode)