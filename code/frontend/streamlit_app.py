
import os
import base64
import json
import requests
import pandas as pd
import streamlit as st
from app.auth import extract_bearer_token

# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="FinSage | Finance Copilot",
    page_icon="💠",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_URL = os.getenv("FINSAGE_API_URL", "http://127.0.0.1:8000")
APP_ROUTER_URL = os.getenv(
    "FINSAGE_ROUTER_URL",
    "https://finsage.cfapps.ap21.hana.ondemand.com"
)


def get_authenticated_access_token():
    """Read the XSUAA user token forwarded by SAP Application Router."""
    try:
        headers = getattr(st.context, "headers", {}) or {}
    except Exception:
        headers = {}

    return extract_bearer_token(headers)


def get_authenticated_user_name():
    token = get_authenticated_access_token()
    if not token:
        return None

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(
            base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
        )
        return claims.get("email") or claims.get("user_name") or claims.get("sub")
    except Exception:
        return None


if not get_authenticated_access_token():
    st.title("Sign in to FinSage")
    st.info("Sign in through SAP BTP to view finance data.")
    st.link_button("Continue with SAP BTP", APP_ROUTER_URL)
    st.stop()


# --------------------------------------------------
# CUSTOM DESIGN
# --------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: #f5f7fb;
}

[data-testid="stSidebar"] {
    background: #101b35;
}

[data-testid="stSidebar"] * {
    color: #ffffff !important;
}

[data-testid="stSidebar"] .stRadio label {
    padding: 9px 12px;
    border-radius: 9px;
}

.main-title {
    font-size: 30px;
    font-weight: 800;
    color: #152544;
    margin-bottom: 2px;
}

.subtitle {
    color: #718096;
    font-size: 14px;
    margin-bottom: 25px;
}

.metric-card {
    background: white;
    border: 1px solid #e7ebf2;
    border-radius: 14px;
    padding: 19px;
    min-height: 120px;
    box-shadow: 0 3px 12px rgba(20,40,80,0.035);
}

.metric-label {
    color: #718096;
    font-size: 13px;
    font-weight: 600;
}

.metric-value {
    color: #172b4d;
    font-size: 27px;
    font-weight: 800;
    margin-top: 9px;
}

.section-title {
    color: #172b4d;
    font-size: 20px;
    font-weight: 750;
    margin: 16px 0 12px 0;
}

.info-card {
    background: white;
    padding: 18px;
    border-radius: 13px;
    border: 1px solid #e7ebf2;
    margin-bottom: 12px;
}

.stButton button {
    border-radius: 9px;
    font-weight: 600;
}

div[data-testid="stChatMessage"] {
    border-radius: 12px;
}

</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "api_status" not in st.session_state:
    st.session_state.api_status = None


# --------------------------------------------------
# API HELPERS
# --------------------------------------------------

def parse_api_response(response):
    content_type = response.headers.get("Content-Type", "")
    if "json" not in content_type.lower():
        raise ValueError(
            "Expected JSON from FinSage API, but received "
            f"{content_type or 'an unknown content type'}. "
            "Sign in through SAP BTP and retry."
        )
    return response.json()


def api_get(endpoint, params=None):
    try:
        headers = {}

        token = get_authenticated_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = requests.get(
            f"{API_URL}{endpoint}",
            params=params,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()
        return parse_api_response(response), None

    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to FinSage API."

    except requests.exceptions.Timeout:
        return None, "The API request timed out."

    except requests.exceptions.HTTPError:
        if response.status_code == 401:
            return None, "Authentication failed. Please check XSUAA access."
        if response.status_code == 403:
            return None, "Your account does not have permission for this operation."

        return None, f"API returned HTTP {response.status_code}: {response.text[:300]}"

    except requests.RequestException as error:
        return None, str(error)

    except (ValueError, KeyError) as error:
        return None, f"Invalid API response: {error}"

    except Exception as error:
        return None, f"Authentication error: {error}"
def api_post(endpoint, payload):
    response = None

    try:
        headers = {}

        token = get_authenticated_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = requests.post(
            f"{API_URL}{endpoint}",
            json=payload,
            headers=headers,
            timeout=60
        )

        response.raise_for_status()
        return parse_api_response(response), None

    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to FinSage API."

    except requests.exceptions.Timeout:
        return None, "The API request timed out."

    except requests.exceptions.HTTPError:
        if response is not None:
            if response.status_code == 401:
                return None, "Authentication failed. Check XSUAA access."
            if response.status_code == 403:
                return None, "Approver permission is required for this action."

            return None, (
                f"API returned HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        return None, "The API request failed."

    except requests.RequestException as error:
        return None, str(error)

    except Exception as error:
        return None, f"Authentication error: {error}"


def to_dataframe(data):
    if isinstance(data, list):
        return pd.DataFrame(data)

    if isinstance(data, dict):
        for key in (
            "invoices",
            "data",
            "exceptions",
            "compliance_report",
            "duplicates",
            "missing_po_numbers",
            "po_amount_mismatches",
            "requiring_review"
        ):
            if isinstance(data.get(key), list):
                return pd.DataFrame(data[key])

        return pd.DataFrame([data])

    return pd.DataFrame()


def render_ai_usage(ai_usage):
    if not isinstance(ai_usage, dict):
        return

    gemini_answer_status = ai_usage.get("gemini_used_for_answer")
    if gemini_answer_status is None:
        status_label = "Not reported"
    else:
        status_label = "Yes" if gemini_answer_status else "No"

    st.caption(f"**Answer generated by Gemini AI:** {status_label}")
    if ai_usage.get("gemini_generation_status") == "FAILED":
        st.warning(
            "Gemini answer generation failed "
            f"({ai_usage.get('gemini_generation_error', 'provider error')}). "
            "A verified policy-text fallback was used."
        )

    with st.expander("How this answer was produced"):
        usage_cols = st.columns(2)
        with usage_cols[0]:
            st.metric(
                "Gemini generated the answer",
                status_label
            )
        with usage_cols[1]:
            st.metric(
                "Gemini used for policy search",
                "Yes" if ai_usage.get("gemini_used_for_retrieval") else "No"
            )
        st.caption(
            "Answer method: "
            + str(ai_usage.get(
                "answer_generation",
                "Not reported by the backend"
            ))
        )
        if ai_usage.get("gemini_model"):
            st.caption("Retrieval model: " + str(ai_usage["gemini_model"]))
        if ai_usage.get("gemini_answer_model"):
            st.caption(
                "Answer model: " + str(ai_usage["gemini_answer_model"])
            )


def money(value):
    try:
        return f"₹{float(value):,.2f}"
    except (ValueError, TypeError):
        return "—"


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:

    st.markdown("# 💠 FinSage")
    st.caption("AGENTIC FINANCE INTELLIGENCE")

    st.divider()

    page = st.radio(
        "WORKSPACE",
        [
            "Overview",
            "AI Finance Copilot",
            "Invoice Monitoring",
            "Expense Compliance",
            "Exception Management",
            "HANA Logs"
        ],
        label_visibility="visible"
    )

    st.divider()

    st.markdown("### System connection")

    authenticated_user = get_authenticated_user_name()
    if authenticated_user:
        st.success(f"Signed in: {authenticated_user}")
        st.markdown(
            '<a href="/logout" target="_self">Logout</a>',
            unsafe_allow_html=True
        )
    else:
        st.info("Sign in is required through SAP BTP")
        st.markdown(
            f'<a href="{APP_ROUTER_URL}" target="_self">Login with SAP BTP</a>',
            unsafe_allow_html=True
        )

    health, health_error = api_get("/health")

    if health:
        st.success("FastAPI: Connected")
        st.caption(f"Version: {health.get('version', 'Unknown')}")
        st.info("SAP HANA: Not checked by the liveness endpoint")
        st.caption("Database access is checked when finance data is requested.")
    else:
        st.error("FastAPI: Disconnected")
        st.info("SAP HANA: Status unknown")
        st.caption("Start the FastAPI backend.")

    st.divider()

    st.caption("FinSage Finance Copilot")
    st.caption("SAP BTP | SAP HANA Cloud")


# --------------------------------------------------
# PAGE HEADER
# --------------------------------------------------

def page_header(title, description):
    st.markdown(
        f'<div class="main-title">{title}</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        f'<div class="subtitle">{description}</div>',
        unsafe_allow_html=True
    )


def metric_card(label, value, icon):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{icon} &nbsp; {label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


# --------------------------------------------------
# OVERVIEW DASHBOARD
# --------------------------------------------------

if page == "Overview":

    page_header(
        "Finance Intelligence Dashboard",
        "Monitor accounts payable, invoice risk and employee expense compliance."
    )

    if st.button("↻ Refresh dashboard"):
        st.rerun()

    summary, summary_error = api_get("/agent/invoices/summary")
    triage, triage_error = api_get("/agent/invoices/triage/report")
    exceptions, exceptions_error = api_get("/agent/expense-exceptions")

    if summary_error:
        st.warning("Invoice summary unavailable: " + summary_error)

    if triage_error:
        st.warning("Invoice triage unavailable: " + triage_error)

    if exceptions_error:
        st.warning("Expense exceptions unavailable: " + exceptions_error)

    if summary is not None:

        summary_df = to_dataframe(summary)

        st.markdown('<div class="section-title">Finance overview</div>',
                    unsafe_allow_html=True)

        # Display available summary fields without inventing metrics.
        st.json(summary)

    if triage is not None:

        duplicate_count = len(triage.get("duplicates", []))
        missing_po_count = len(triage.get("missing_po_numbers", []))
        mismatch_count = len(triage.get("po_amount_mismatches", []))
        review_count = len(triage.get("requiring_review", []))

        st.markdown('<div class="section-title">Invoice risk indicators</div>',
                    unsafe_allow_html=True)

        cols = st.columns(4)

        with cols[0]:
            metric_card("Duplicate groups", duplicate_count, "🔁")

        with cols[1]:
            metric_card("Missing PO", missing_po_count, "📄")

        with cols[2]:
            metric_card("PO mismatches", mismatch_count, "⚠️")

        with cols[3]:
            metric_card("Needs review", review_count, "🔍")

        chart_data = pd.DataFrame({
            "Risk category": [
                "Duplicates",
                "Missing PO",
                "PO mismatches",
                "Needs review"
            ],
            "Count": [
                duplicate_count,
                missing_po_count,
                mismatch_count,
                review_count
            ]
        })

        st.markdown('<div class="section-title">Invoice risk distribution</div>',
                    unsafe_allow_html=True)

        st.bar_chart(
            chart_data.set_index("Risk category"),
            use_container_width=True
        )

    if exceptions is not None:

        exception_df = to_dataframe(exceptions)

        st.markdown('<div class="section-title">Recent expense exceptions</div>',
                    unsafe_allow_html=True)

        if not exception_df.empty:
            st.dataframe(
                exception_df.head(10),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No expense exception records returned.")


# --------------------------------------------------
# AI FINANCE COPILOT
# --------------------------------------------------

elif page == "AI Finance Copilot":

    page_header(
        "AI Finance Copilot",
        "Ask questions about finance policies, invoices, vendors and expenses."
    )

    st.markdown("""
    <div class="info-card">
        <b>Ask FinSage</b><br>
        <span style="color:#718096">
        Get answers using available finance records and policy evidence.
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Region selector
    selected_region = st.selectbox(
        "Select finance policy region",
        options=["India", "USA"],
        index=0,
        key="copilot_region"
    )

    suggested_questions = [
        "What is the hotel expense limit?",
        "Find duplicate invoices.",
        "Which invoices have PO mismatches?",
        "Show invoices with missing purchase orders.",
        "What are the vendor onboarding requirements?"
    ]

    with st.expander("Suggested questions"):
        for question in suggested_questions:
            if st.button(question, key=f"suggest_{question}"):
                st.session_state.pending_question = question

    for message in st.session_state.chat_history:

        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message.get("citations"):
                with st.expander("View evidence citations"):
                    st.json(message["citations"])

            if message.get("ai_usage"):
                render_ai_usage(message["ai_usage"])

    prompt = st.chat_input("Ask a finance question...")

    if "pending_question" in st.session_state:
        prompt = st.session_state.pop("pending_question")

    if prompt:

        st.session_state.chat_history.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):

            with st.spinner("FinSage is analysing your request..."):

                result, error = api_post(
                    "/agent/ask",
                    {
                        "question": prompt,
                        "region": selected_region
                    }
                )

            if error:
                answer = f"Unable to process the request: {error}"
                citations = []

            else:
                answer = result.get("answer", "No answer returned.")
                citations = result.get("citations", [])

                st.markdown(
                    f"**Intent:** `{result.get('intent', 'UNKNOWN')}`"
                )

                if result.get("evidence_verification"):
                    st.caption("Evidence verification")
                    st.json(result["evidence_verification"])

                if citations:
                    with st.expander("Evidence citations"):
                        st.json(citations)

            st.markdown(answer)

            ai_usage = result.get("ai_usage") if not error else None
            if ai_usage:
                render_ai_usage(ai_usage)
            elif not error:
                st.warning(
                    "AI usage details are not available. "
                    "Deploy the updated backend to show them."
                )

            st.session_state.chat_history.append({
                "role": "assistant",
                "content": answer,
                "citations": citations,
                "ai_usage": ai_usage
            })

        if st.button("Clear conversation"):
            st.session_state.chat_history = []
            st.rerun()

        st.divider()

# --------------------------------------------------
# INVOICE MONITORING


# --------------------------------------------------
# INVOICE MONITORING
# --------------------------------------------------

elif page == "Invoice Monitoring":

    page_header(
        "Invoice Monitoring",
        "Review invoice details, payment information and automated risk checks."
    )

    tab1, tab2, tab3, tab4 = st.tabs([
        "Invoice Summary",
        "Risk Analysis",
        "Invoice Lookup",
        "Flag Invoice"
    ])

    # --------------------------------------------------
    # TAB 1: INVOICE SUMMARY
    # --------------------------------------------------

    with tab1:

        summary, error = api_get("/agent/invoices/summary")

        if error:
            st.error(error)
        else:
            st.json(summary)

    # --------------------------------------------------
    # TAB 2: INVOICE RISK ANALYSIS
    # --------------------------------------------------

    with tab2:

        report, error = api_get("/agent/invoices/triage/report")

        if error:
            st.error(error)
        else:
            categories = [
                ("Duplicate invoices", "duplicates"),
                ("Missing purchase orders", "missing_po_numbers"),
                ("Invoices exceeding approved PO amount", "po_amount_mismatches"),
                ("Invoices requiring review", "requiring_review")
            ]

            for title, key in categories:

                records = report.get(key, [])

                with st.expander(f"{title} ({len(records)})"):

                    if records:
                        st.dataframe(
                            pd.DataFrame(records),
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.success("No records found.")

    # --------------------------------------------------
    # TAB 3: INVOICE LOOKUP
    # --------------------------------------------------

    with tab3:

        invoice_id = st.text_input(
            "Enter invoice ID",
            placeholder="Example: INV004",
            key="invoice_lookup_id"
        )

        if st.button("Search invoice"):

            if invoice_id.strip():

                invoice, error = api_get(
                    f"/agent/invoices/{invoice_id.strip()}"
                )

                if error:
                    st.error(error)
                else:
                    st.json(invoice)

            else:
                st.warning("Please enter an invoice ID.")

    # --------------------------------------------------
    # TAB 4: FLAG INVOICE
    # --------------------------------------------------

    with tab4:

        st.markdown("### Flag an invoice for compliance review")

        st.info(
            "Flagging an invoice updates its status in SAP HANA. "
            "Review the invoice details and confirm before submitting."
        )

        with st.form("flag_invoice_form"):

            flag_invoice_id = st.text_input(
                "Invoice ID",
                placeholder="Example: INV004"
            )

            flag_reason = st.text_area(
                "Reason for flagging",
                placeholder="Explain why this invoice requires compliance review."
            )

            confirm_flag = st.checkbox(
                "I confirm that this invoice should be flagged for review."
            )

            submit_flag = st.form_submit_button(
                "Confirm and Flag Invoice",
                type="primary"
            )

        if submit_flag:

            if not flag_invoice_id.strip():
                st.error("Please enter an invoice ID.")

            elif not flag_reason.strip():
                st.error("Please provide a reason for flagging.")

            elif not confirm_flag:
                st.warning(
                    "Please confirm before flagging the invoice."
                )

            else:

                payload = {
                    "invoice_id": flag_invoice_id.strip(),
                    "reason": flag_reason.strip(),
                    "confirmed": True
                }

                with st.spinner("Submitting invoice flag..."):

                    result, error = api_post(
                        "/agent/flag-invoice",
                        payload
                    )

                if error:
                    st.error(error)

                elif result.get("success"):

                    st.success(
                        result.get(
                            "message",
                            "Invoice successfully flagged."
                        )
                    )

                    st.json(result)

                else:
                    st.warning(
                        result.get(
                            "message",
                            "Invoice could not be flagged."
                        )
                    )
#---------------------------------------------
# EXPENSE COMPLIANCE
# --------------------------------------------------

elif page == "Expense Compliance":

    page_header(
        "Expense Compliance Centre",
        "Review employee expense claims against configured compliance rules."
    )

    report, error = api_get("/agent/expenses/compliance")

    if error:
        st.error(error)

    else:

        st.metric(
            "Total recorded exceptions",
            report.get("total_exceptions", 0)
        )

        st.caption(
            "Compliance screening scope: "
            + str(report.get(
                "verification_scope",
                "Limited reference checks; inspect verification notes."
            ))
        )

        compliance_df = to_dataframe(report)

        if not compliance_df.empty:

            search = st.text_input(
                "Search compliance records",
                placeholder="Employee, category or exception..."
            )

            if search:
                mask = compliance_df.astype(str).apply(
                    lambda column: column.str.contains(
                        search,
                        case=False,
                        na=False
                    )
                ).any(axis=1)

                compliance_df = compliance_df[mask]

            st.dataframe(
                compliance_df,
                use_container_width=True,
                hide_index=True
            )

            if "severity" in compliance_df.columns:

                severity_counts = (
                    compliance_df["severity"]
                    .fillna("Unspecified")
                    .value_counts()
                )

                st.markdown("### Exception severity")
                st.bar_chart(severity_counts)

        else:
            st.info("No compliance records returned.")


# --------------------------------------------------
# EXCEPTION MANAGEMENT
# --------------------------------------------------

elif page == "Exception Management":

    page_header(
        "Expense Exception Management",
        "Review existing exceptions and submit a new confirmed exception."
    )

    existing, error = api_get("/agent/expense-exceptions")

    if error:
        st.error(error)
    else:
        exception_df = to_dataframe(existing)

        st.markdown("### Existing exceptions")

        if not exception_df.empty:
            st.dataframe(
                exception_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No exception records returned.")

    st.divider()

    st.markdown("### Log a new expense exception")

    with st.form("expense_exception_form"):

        col1, col2 = st.columns(2)

        with col1:
            employee_id = st.text_input("Employee ID")
            employee_name = st.text_input("Employee name")
            category = st.selectbox(
                "Expense category",
                ["HOTEL", "MEAL", "TRANSPORT", "TRAVEL", "OTHER"]
            )
            amount = st.number_input(
                "Expense amount",
                min_value=0.01,
                value=1000.0
            )
            nights_value = st.number_input(
                "Hotel nights (required for hotel)",
                min_value=1,
                value=1,
                step=1
            )
            days_value = st.number_input(
                "Meal days (required for meals)",
                min_value=1,
                value=1,
                step=1
            )
            expense_date = st.date_input("Expense date")

        with col2:
            region = st.selectbox("Region", ["IN", "USA"])
            currency = st.selectbox(
                "Currency",
                ["INR", "USD"],
                index=0 if region == "IN" else 1
            )
            policy_reference = st.text_input("Policy reference")
            receipt_status = st.selectbox(
                "Receipt status (submitter-reported)",
                ["UNKNOWN", "SUBMITTED", "MISSING"]
            )
            severity = st.selectbox(
                "Reported severity",
                ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            )
            reason = st.text_area("Reason for exception")

        confirmed = st.checkbox(
            "I confirm that this exception should be submitted."
        )

        submitted = st.form_submit_button(
            "Submit expense exception",
            type="primary"
        )

        if submitted:

            if not all([
                employee_id,
                employee_name,
                policy_reference,
                reason
            ]):
                st.error("Please complete all required fields.")

            elif not confirmed:
                st.warning("Please confirm before submitting.")

            else:

                payload = {
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                    "expense_category": category,
                    "expense_amount": amount,
                    "currency": currency,
                    "expense_date": str(expense_date),
                    "region": region,
                    "policy_reference": policy_reference,
                    "exception_reason": reason,
                    "severity": severity,
                    "nights": (
                        int(nights_value) if category == "HOTEL" else None
                    ),
                    "days": (
                        int(days_value)
                        if category in ("MEAL", "MEALS")
                        else None
                    ),
                    "receipt_status": receipt_status,
                    "confirmed": True
                }

                result, error = api_post(
                    "/agent/log-exception",
                    payload
                )

                if error:
                    st.error(error)
                else:
                    st.success("Expense exception submitted.")
                    st.json(result)


# --------------------------------------------------
# HANA LOGS AND AI USAGE
# --------------------------------------------------

elif page == "HANA Logs":

    page_header(
        "HANA Logs",
        "Review persisted agent activity, invoice flags, and expense exceptions."
    )

    if st.button("Refresh HANA logs"):
        st.rerun()

    traces_tab, flags_tab, exceptions_tab = st.tabs([
        "Agent Traces",
        "Invoice Flags",
        "Expense Exceptions"
    ])

    with traces_tab:
        st.caption(
            "Purpose: audit each Copilot request, its outcome, and the "
            "processing stages recorded in SAP HANA."
        )
        trace_data, trace_error = api_get(
            "/agent/traces",
            params={"limit": 50}
        )

        if trace_error:
            st.error(f"Could not load agent traces: {trace_error}")
        else:
            traces = trace_data.get("traces", [])
            st.metric("Traces loaded", trace_data.get("total_traces", 0))

            if traces:
                trace_rows = [
                    {
                        "Trace ID": trace.get("trace_id"),
                        "Request type": trace.get("request_type"),
                        "Request summary": trace.get("request_summary"),
                        "Started": trace.get("started_at"),
                        "Finished": trace.get("finished_at"),
                        "Status": trace.get("status"),
                        "Decision": trace.get("decision")
                    }
                    for trace in traces
                ]
                st.dataframe(
                    pd.DataFrame(trace_rows),
                    use_container_width=True,
                    hide_index=True
                )

                selected_index = st.selectbox(
                    "View trace stages",
                    options=range(len(traces)),
                    format_func=lambda index: (
                        f"{traces[index].get('trace_id')} — "
                        f"{traces[index].get('request_summary', '')}"
                    )
                )
                selected_trace = traces[selected_index]
                stage_purposes = {
                    "INTENT_CLASSIFICATION": "Identify the finance request type.",
                    "FINANCE_TOOL_EXECUTION": "Retrieve or process the requested finance data.",
                    "EVIDENCE_VERIFICATION": "Check evidence availability and citations.",
                    "RESPONSE_GENERATION": "Record the response decision.",
                    "REQUEST_ERROR": "Record a failed request stage."
                }
                stages = selected_trace.get("stages", [])
                if stages:
                    stage_rows = [
                        {
                            "Stage": stage.get("stage"),
                            "Purpose": stage_purposes.get(
                                stage.get("stage"),
                                "Processing stage recorded by FinSage."
                            ),
                            "Status": stage.get("status"),
                            "Time": stage.get("timestamp"),
                            "Details": json.dumps(
                                stage.get("details", {}),
                                ensure_ascii=False
                            )
                        }
                        for stage in stages
                    ]
                    st.dataframe(
                        pd.DataFrame(stage_rows),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No processing stages were recorded for this trace.")
            else:
                st.info("No agent traces are available in HANA yet.")

    with flags_tab:
        st.caption(
            "Purpose: keep a history of each invoice flag, including its "
            "reason and timestamp. Each row represents one flag event."
        )
        flag_data, flag_error = api_get(
            "/agent/invoice-flags",
            params={"limit": 100}
        )

        if flag_error:
            st.error(f"Could not load invoice flag history: {flag_error}")
        else:
            flags = flag_data.get("flags", [])
            st.metric("Flag events loaded", flag_data.get("total_flags", 0))
            if flags:
                flag_rows = [
                    {
                        "Case reference": flag.get("case_ref"),
                        "Invoice ID": flag.get("invoice_id"),
                        "Reason": flag.get("reason"),
                        "Status": flag.get("status"),
                        "Flagged at": flag.get("flagged_at")
                    }
                    for flag in flags
                ]
                st.dataframe(
                    pd.DataFrame(flag_rows),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No invoice flag events are available in HANA yet.")

    with exceptions_tab:
        st.caption(
            "Purpose: review expense exceptions submitted for finance "
            "compliance review."
        )
        exceptions, exceptions_error = api_get("/agent/expense-exceptions")

        if exceptions_error:
            st.error(f"Could not load expense exceptions: {exceptions_error}")
        else:
            exception_df = to_dataframe(exceptions)
            st.metric("Exceptions loaded", len(exception_df))
            if not exception_df.empty:
                st.dataframe(
                    exception_df.rename(columns={
                        "exception_id": "Exception ID",
                        "employee_id": "Employee ID",
                        "employee_name": "Employee",
                        "expense_category": "Category",
                        "expense_amount": "Amount",
                        "currency": "Currency",
                        "expense_date": "Expense date",
                        "region": "Region",
                        "policy_reference": "Policy reference",
                        "exception_reason": "Reason",
                        "severity": "Severity",
                        "approval_status": "Status",
                        "created_at": "Created at"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No expense exceptions are available in HANA yet.")


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "FinSage | Agentic AI Accounts Payable & Expense Compliance Copilot | "
    "Powered by FastAPI and SAP HANA Cloud"
)
