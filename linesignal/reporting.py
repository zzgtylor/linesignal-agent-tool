"""Render conclusions from validated evidence, without generative expansion."""
LABELS={'pressure_bar':'air pressure','motor_current_a':'motor current','photoeye_blocked':'photoeye blocked'}
CHECKS={'pressure_bar':'Ask a trained operator to inspect the air supply, regulator and leak records under site isolation procedures.',
        'motor_current_a':'Ask a trained operator to review mechanical load and motor records under site isolation procedures.',
        'photoeye_blocked':'Ask a trained operator to inspect sensor alignment and obstruction records under site isolation procedures.'}


def render_brief(result):
    lines=[f"LineSignal | {result.get('incident_id','incident')} | {'synthetic demo data' if result.get('synthetic') else 'evidence unavailable'}"]
    status=result['status']
    if status=='insufficient_evidence':
        lines+=['Cannot establish the event sequence or give an incident-specific diagnosis.',
                'Data quality: '+', '.join(result['reason_codes'])+'.',
                'Next check: obtain a complete 60-second window of UTC telemetry at 2-second intervals.']
    elif status in {'observed','simultaneous_deviations','no_pre_stop_anomaly'}:
        if status=='simultaneous_deviations':
            lines.append('The earliest signals are tied and cannot be ordered at the available sampling resolution.')
        elif status=='no_pre_stop_anomaly':
            lines.append('No sustained pre-stop threshold deviation was observed among the monitored signals; the cause remains unknown.')
        else:
            first=result['first_observed']
            lines.append(f"First observed sustained deviation: {LABELS[first['metric']]}, {first['lead_seconds']} seconds before the recorded stop.")
        for item in result['evidence']:
            lines.append(f"[{item['evidence_id']}] {item['at']}: {LABELS[item['metric']]} changed from {item['baseline_value']} to {item['value']} ({item['threshold']}); two consecutive samples, {item['lead_seconds']} seconds before stop.")
        if result['first_observed']:
            lines.append('Next check: '+CHECKS[result['first_observed']['metric']])
        else:
            lines.append('Next check: collect higher-resolution or additional signals before selecting a cause.')
    else:
        raise ValueError('Unrecognized evidence status')
    lines.append('Temporal order is not causal proof. Read-only analysis; no restart or machine-control command is issued.')
    source=result.get('source')
    if source:
        lines.append(f"Source: Amazon S3 / {source['key']} | SHA-256 {source['sha256']}")
    return '\n\n'.join(lines)
