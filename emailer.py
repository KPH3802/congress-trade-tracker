"""
Congressional Trading Tracker - Email Reporter
===============================================
Sends instant email alerts for congressional trading patterns.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict
import json
import config
import database


def send_email(subject: str, body: str, html_body: str = None) -> bool:
    """Send an email using Gmail SMTP."""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = config.EMAIL_SENDER
        msg['To'] = config.EMAIL_RECIPIENT
        
        text_part = MIMEText(body, 'plain')
        msg.attach(text_part)
        
        if html_body:
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
        
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            server.send_message(msg)
        
        print(f"✓ Email sent to {config.EMAIL_RECIPIENT}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("ERROR: Gmail authentication failed!")
        return False
    except Exception as e:
        print(f"ERROR sending email: {e}")
        return False


def format_alert_html(alerts: List[Dict]) -> str:
    """Format alerts as an HTML email."""
    
    # Count buy vs sell
    buy_alerts = [a for a in alerts if a['trade_type'] == 'buy']
    sell_alerts = [a for a in alerts if a['trade_type'] == 'sell']
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header p {{ margin: 5px 0 0 0; opacity: 0.9; }}
            .content {{ padding: 20px; background: #f8f9fa; }}
            .alert-card {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .alert-card.buy {{ border-left: 5px solid #38a169; }}
            .alert-card.sell {{ border-left: 5px solid #e53e3e; }}
            .ticker {{ font-size: 28px; font-weight: bold; color: #1a365d; }}
            .trade-type {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 14px; font-weight: bold; margin-left: 10px; }}
            .trade-type.buy {{ background: #c6f6d5; color: #276749; }}
            .trade-type.sell {{ background: #fed7d7; color: #c53030; }}
            .score {{ font-size: 18px; color: #718096; margin-top: 5px; }}
            .signals {{ margin: 15px 0; }}
            .signal {{ display: inline-block; background: #edf2f7; padding: 4px 10px; border-radius: 4px; margin: 2px 4px 2px 0; font-size: 13px; }}
            .signal.strong {{ background: #fef3c7; color: #92400e; }}
            .signal.bipartisan {{ background: #e9d5ff; color: #6b21a8; }}
            .politicians {{ margin-top: 15px; }}
            .politician {{ padding: 10px; background: #f7fafc; border-radius: 4px; margin: 8px 0; }}
            .politician-name {{ font-weight: bold; }}
            .politician-details {{ color: #718096; font-size: 14px; }}
            .party-d {{ color: #2b6cb0; }}
            .party-r {{ color: #c53030; }}
            .party-i {{ color: #718096; }}
            .meta {{ margin-top: 15px; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 14px; color: #718096; }}
            .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #a0aec0; }}
            .summary-box {{ background: white; border-radius: 8px; padding: 15px; margin-bottom: 20px; display: flex; justify-content: space-around; text-align: center; }}
            .summary-stat {{ }}
            .summary-stat .number {{ font-size: 32px; font-weight: bold; color: #1a365d; }}
            .summary-stat .label {{ font-size: 14px; color: #718096; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🏛️ Congressional Trading Alert</h1>
            <p>{len(alerts)} pattern(s) detected • {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
        </div>
        
        <div class="content">
            <div class="summary-box">
                <div class="summary-stat">
                    <div class="number">{len(alerts)}</div>
                    <div class="label">Total Alerts</div>
                </div>
                <div class="summary-stat">
                    <div class="number" style="color: #38a169;">{len(buy_alerts)}</div>
                    <div class="label">Buy Clusters</div>
                </div>
                <div class="summary-stat">
                    <div class="number" style="color: #e53e3e;">{len(sell_alerts)}</div>
                    <div class="label">Sell Clusters</div>
                </div>
            </div>
    """
    
    for alert in alerts:
        card_class = 'buy' if alert['trade_type'] == 'buy' else 'sell'
        type_emoji = '🟢' if alert['trade_type'] == 'buy' else '🔴'
        
        # Format signals
        signals_html = ""
        for signal in alert['signals']:
            signal_class = "signal"
            if 'Cluster' in signal or 'Bipartisan' in signal:
                signal_class += " strong"
            if 'Bipartisan' in signal:
                signal_class += " bipartisan"
            signals_html += f'<span class="{signal_class}">{signal}</span>'
        
        # Format politicians
        politicians_html = ""
        for txn in alert['transactions']:
            party = txn.get('party', '?')
            party_class = f"party-{party.lower()}" if party in ['D', 'R', 'I'] else ""
            state = txn.get('state', '??')
            chamber = txn.get('chamber', '')
            amount = txn.get('amount_range', 'Unknown')
            date = txn.get('trade_date', 'Unknown')
            company = txn.get('company', '')[:50]  # Truncate
            
            politicians_html += f"""
            <div class="politician">
                <div class="politician-name">
                    <span class="{party_class}">{txn['politician']}</span>
                    <span style="color: #a0aec0;">({party}-{state}) • {chamber}</span>
                </div>
                <div class="politician-details">
                    📅 {date} • 💰 {amount}
                </div>
            </div>
            """
        
        # Calculate total value for display
        if alert['total_value_high'] >= 1000000:
            value_display = f"${alert['total_value_low']/1000000:.1f}M - ${alert['total_value_high']/1000000:.1f}M"
        else:
            value_display = f"${alert['total_value_low']:,} - ${alert['total_value_high']:,}"
        
        html += f"""
            <div class="alert-card {card_class}">
                <div>
                    <span class="ticker">{alert['ticker']}</span>
                    <span class="trade-type {card_class}">{type_emoji} {alert['trade_type'].upper()}</span>
                </div>
                <div class="score">
                    Score: {alert['score']} • {alert['politician_count']} Politicians • {value_display} total
                </div>
                
                <div class="signals">
                    {signals_html}
                </div>
                
                <div class="politicians">
                    <strong>Trades:</strong>
                    {politicians_html}
                </div>
                
                <div class="meta">
                    📆 Date Range: {alert['date_range']}
                </div>
            </div>
        """
    
    html += """
            <div class="footer">
                <p>Congressional Trading Tracker</p>
                <p>Data sourced from official House and Senate financial disclosures</p>
                <p style="margin-top: 10px;">
                    <strong>Signal Guide:</strong> 
                    🔴 Cluster = 3+ politicians • 
                    Bipartisan = Both parties • 
                    Committee = Relevant oversight
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def format_alert_text(alerts: List[Dict]) -> str:
    """Format alerts as plain text."""
    lines = []
    lines.append("=" * 60)
    lines.append("🏛️ CONGRESSIONAL TRADING ALERT")
    lines.append(f"   {len(alerts)} pattern(s) detected")
    lines.append(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)
    
    for alert in alerts:
        emoji = "🟢" if alert['trade_type'] == 'buy' else "🔴"
        lines.append("")
        lines.append(f"{emoji} {alert['ticker']} - {alert['politician_count']} Politicians {alert['trade_type'].upper()}")
        lines.append(f"   Score: {alert['score']}")
        lines.append(f"   Signals: {', '.join(alert['signals'])}")
        lines.append(f"   Date Range: {alert['date_range']}")
        lines.append(f"   Est. Value: ${alert['total_value_low']:,} - ${alert['total_value_high']:,}")
        lines.append("   Trades:")
        
        for txn in alert['transactions']:
            party = txn.get('party', '?')
            state = txn.get('state', '??')
            amount = txn.get('amount_range', 'Unknown')
            date = txn.get('trade_date', 'Unknown')
            lines.append(f"      • {txn['politician']} ({party}-{state}): {amount} on {date}")
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def send_alerts(alerts: List[Dict], dry_run: bool = False) -> bool:
    """
    Send email alerts for detected patterns.
    
    Args:
        alerts: List of alert dictionaries from analyzer
        dry_run: If True, print instead of sending
    
    Returns:
        True if sent successfully
    """
    if not alerts:
        print("No alerts to send.")
        return False
    
    # Create subject line
    tickers = list(set(a['ticker'] for a in alerts))
    buy_count = len([a for a in alerts if a['trade_type'] == 'buy'])
    sell_count = len([a for a in alerts if a['trade_type'] == 'sell'])
    
    if len(tickers) == 1:
        subject = f"🏛️ Congress Alert: {tickers[0]} - {alerts[0]['politician_count']} Politicians"
    else:
        subject = f"🏛️ Congress Alert: {len(alerts)} Patterns ({buy_count} Buy, {sell_count} Sell)"
    
    # Add top ticker to subject if multiple
    if len(tickers) > 1:
        subject += f" - {', '.join(tickers[:3])}"
        if len(tickers) > 3:
            subject += f" +{len(tickers)-3} more"
    
    # Generate email content
    text_body = format_alert_text(alerts)
    html_body = format_alert_html(alerts)
    
    if dry_run:
        print(f"\n{'='*60}")
        print("DRY RUN - Would send email:")
        print(f"{'='*60}")
        print(f"Subject: {subject}")
        print(f"To: {config.EMAIL_RECIPIENT}")
        print(f"\n{text_body}")
        return True
    
    # Send email
    success = send_email(subject, text_body, html_body)
    
    # Record alerts as sent
    if success:
        for alert in alerts:
            database.record_alert_sent(
                alert_type='cluster',
                ticker=alert['ticker'],
                alert_hash=alert['alert_hash'],
                politicians=json.dumps(alert['politicians']),
                score=alert['score']
            )
    
    return success


def send_daily_summary(stats: Dict, dry_run: bool = False) -> bool:
    """
    Send a daily summary email (optional - for monitoring).
    """
    subject = f"📊 Congress Tracker Daily Summary - {datetime.now().strftime('%Y-%m-%d')}"
    
    text_body = f"""
Congressional Trading Tracker - Daily Summary
{datetime.now().strftime('%Y-%m-%d %H:%M')}

Database Status:
  Total transactions: {stats.get('total_transactions', 0):,}
  Unique politicians: {stats.get('unique_politicians', 0)}
  Unique tickers: {stats.get('unique_tickers', 0)}
  
Recent Activity:
  Transactions last 7 days: {stats.get('transactions_last_7_days', 0)}
  Alerts sent: {stats.get('alerts_sent', 0)}
  
Date Range: {stats.get('earliest_trade', 'N/A')} to {stats.get('latest_trade', 'N/A')}
"""
    
    if dry_run:
        print(f"Subject: {subject}")
        print(text_body)
        return True
    
    return send_email(subject, text_body)


# =============================================================================
# DAILY ANALYSIS REPORT - All 10 Alert Types
# =============================================================================

def format_analysis_report_html(results: Dict) -> str:
    """
    Format the full analysis report (all 10 alert types) as HTML email.
    
    Args:
        results: Output from analyzer.run_all_analysis()
    """
    summary = results.get('summary', {})
    alerts = results.get('alerts', [])
    
    # Group alerts by type
    alert_groups = {
        'CLUSTER': [],
        'BIPARTISAN': [],
        'COMMITTEE_RELEVANT': [],
        'LEADERSHIP_TRADE': [],
        'LARGE_TRADE': [],
        'SECTOR_SURGE': [],
        'REPEAT_BUYER': [],
        'NEW_POSITION': [],
        'PRE_EARNINGS': [],
        'AGAINST_MARKET': []
    }
    
    for alert in alerts:
        alert_type = alert.get('type', 'UNKNOWN')
        if alert_type in alert_groups:
            alert_groups[alert_type].append(alert)
    
    # Priority colors
    priority_colors = {
        'HIGH': '#e53e3e',
        'MEDIUM': '#dd6b20', 
        'LOW': '#718096'
    }
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 0; }}
            .header {{ background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%); color: white; padding: 25px; }}
            .header h1 {{ margin: 0; font-size: 26px; }}
            .header p {{ margin: 8px 0 0 0; opacity: 0.9; font-size: 14px; }}
            .content {{ padding: 20px; background: #f8f9fa; }}
            
            .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 25px; }}
            .summary-box {{ background: white; border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            .summary-box .number {{ font-size: 28px; font-weight: bold; color: #1a365d; }}
            .summary-box .label {{ font-size: 12px; color: #718096; text-transform: uppercase; }}
            .summary-box.high .number {{ color: #e53e3e; }}
            .summary-box.medium .number {{ color: #dd6b20; }}
            
            .section {{ margin-bottom: 25px; }}
            .section-header {{ background: #2d3748; color: white; padding: 12px 15px; border-radius: 8px 8px 0 0; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }}
            .section-header .count {{ background: rgba(255,255,255,0.2); padding: 2px 10px; border-radius: 12px; font-size: 14px; }}
            .section-body {{ background: white; border-radius: 0 0 8px 8px; }}
            .section-empty {{ padding: 20px; color: #a0aec0; text-align: center; font-style: italic; }}
            
            .alert-row {{ padding: 15px; border-bottom: 1px solid #e2e8f0; }}
            .alert-row:last-child {{ border-bottom: none; }}
            .alert-row:hover {{ background: #f7fafc; }}
            
            .priority-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; color: white; margin-right: 8px; }}
            .priority-HIGH {{ background: #e53e3e; }}
            .priority-MEDIUM {{ background: #dd6b20; }}
            .priority-LOW {{ background: #718096; }}
            
            .ticker {{ font-size: 18px; font-weight: bold; color: #1a365d; }}
            .politician {{ font-weight: 600; color: #2d3748; }}
            .detail {{ color: #718096; font-size: 13px; margin-top: 5px; }}
            .highlight {{ background: #fef3c7; padding: 2px 6px; border-radius: 3px; }}
            
            .trade-buy {{ color: #276749; }}
            .trade-sell {{ color: #c53030; }}
            
            .party-r {{ color: #c53030; font-weight: bold; }}
            .party-d {{ color: #2b6cb0; font-weight: bold; }}
            
            .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #a0aec0; background: #f8f9fa; }}
            
            .no-alerts {{ background: white; border-radius: 8px; padding: 40px; text-align: center; color: #718096; }}
            .no-alerts h2 {{ color: #2d3748; margin-bottom: 10px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🏛️ Congressional Trading Analysis</h1>
            <p>Daily Report • {datetime.now().strftime('%B %d, %Y at %I:%M %p')} • {results.get('transaction_count', 0)} transactions analyzed</p>
        </div>
        
        <div class="content">
            <!-- Summary Stats -->
            <div class="summary-grid">
                <div class="summary-box">
                    <div class="number">{summary.get('total_alerts', 0)}</div>
                    <div class="label">Total Alerts</div>
                </div>
                <div class="summary-box high">
                    <div class="number">{summary.get('high_priority', 0)}</div>
                    <div class="label">🔴 High Priority</div>
                </div>
                <div class="summary-box medium">
                    <div class="number">{summary.get('medium_priority', 0)}</div>
                    <div class="label">🟠 Medium</div>
                </div>
                <div class="summary-box">
                    <div class="number">{summary.get('low_priority', 0)}</div>
                    <div class="label">⚪ Low</div>
                </div>
            </div>
    """
    
    # If no alerts at all
    if summary.get('total_alerts', 0) == 0:
        html += """
            <div class="no-alerts">
                <h2>✅ No Notable Patterns Detected</h2>
                <p>No significant trading patterns were found in the analyzed transactions.</p>
            </div>
        """
    else:
        # HIGH PRIORITY ALERTS - Leadership, Against-Market, Pre-Earnings, Bipartisan
        
        # Section: Bipartisan Trades (NEW - Alert #10)
        bipartisan_alerts = alert_groups['BIPARTISAN']
        html += f"""
            <div class="section">
                <div class="section-header" style="background: #6b21a8;">
                    🤝 Bipartisan Buying
                    <span class="count">{len(bipartisan_alerts)}</span>
                </div>
                <div class="section-body">
        """
        if bipartisan_alerts:
            for alert in bipartisan_alerts:
                est_total = alert.get('estimated_total_amount', 0)
                if est_total >= 1000000:
                    amount_display = f"${est_total/1000000:.1f}M"
                elif est_total >= 1000:
                    amount_display = f"${est_total/1000:.0f}K"
                else:
                    amount_display = f"${est_total:,.0f}"
                html += f"""
                    <div class="alert-row">
                        <span class="priority-badge priority-{alert.get('priority', 'HIGH')}">{alert.get('priority', 'HIGH')}</span>
                        <span class="ticker">{alert.get('ticker', 'N/A')}</span>
                        <span style="color:#6b21a8;font-weight:bold;margin-left:10px;">Both Parties Buying</span>
                        <div class="detail">
                            <span class="party-r">Republicans ({alert.get('republican_count', 0)})</span>: {', '.join(alert.get('republican_politicians', [])[:3])}{'...' if len(alert.get('republican_politicians', [])) > 3 else ''}
                        </div>
                        <div class="detail">
                            <span class="party-d">Democrats ({alert.get('democrat_count', 0)})</span>: {', '.join(alert.get('democrat_politicians', [])[:3])}{'...' if len(alert.get('democrat_politicians', [])) > 3 else ''}
                        </div>
                        <div class="detail">
                            Total: {alert.get('total_politicians', 0)} politicians • Est. {amount_display}
                        </div>
                    </div>
                """
        else:
            html += '<div class="section-empty">No bipartisan buying detected</div>'
        html += "</div></div>"
        
        # Section: Leadership Trades
        leadership_alerts = alert_groups['LEADERSHIP_TRADE']
        html += f"""
            <div class="section">
                <div class="section-header" style="background: #744210;">
                    👑 Leadership Trades
                    <span class="count">{len(leadership_alerts)}</span>
                </div>
                <div class="section-body">
        """
        if leadership_alerts:
            for alert in leadership_alerts:
                trade_class = 'trade-buy' if alert.get('trade_type', '').lower() in ['purchase', 'buy'] else 'trade-sell'
                html += f"""
                    <div class="alert-row">
                        <span class="priority-badge priority-{alert.get('priority', 'MEDIUM')}">{alert.get('priority', 'MEDIUM')}</span>
                        <span class="ticker">{alert.get('ticker', 'N/A')}</span>
                        <span class="{trade_class}" style="margin-left: 10px; font-weight: bold;">
                            {alert.get('trade_type', 'N/A').upper()}
                        </span>
                        <div class="detail">
                            <span class="politician">{alert.get('politician', 'Unknown')}</span> • 
                            <span class="highlight">{alert.get('position', 'Leadership')}</span> •
                            {alert.get('amount_range', 'Unknown')}
                        </div>
                    </div>
                """
        else:
            html += '<div class="section-empty">No leadership trades detected</div>'
        html += "</div></div>"
        
        # Section: Against-Market Trades
        against_market_alerts = alert_groups['AGAINST_MARKET']
        html += f"""
            <div class="section">
                <div class="section-header" style="background: #9c4221;">
                    📉 Against-the-Market Trades
                    <span class="count">{len(against_market_alerts)}</span>
                </div>
                <div class="section-body">
        """
        if against_market_alerts:
            for alert in against_market_alerts:
                trade_class = 'trade-buy' if alert.get('trade_type', '').lower() in ['purchase', 'buy'] else 'trade-sell'
                html += f"""
                    <div class="alert-row">
                        <span class="priority-badge priority-{alert.get('priority', 'MEDIUM')}">{alert.get('priority', 'MEDIUM')}</span>
                        <span class="ticker">{alert.get('ticker', 'N/A')}</span>
                        <span class="{trade_class}" style="margin-left: 10px; font-weight: bold;">
                            {alert.get('trade_type', 'N/A').upper()}
                        </span>
                        <div class="detail">
                            <span class="politician">{alert.get('politician', 'Unknown')}</span> • 
                            <span class="highlight">{alert.get('reason', 'Price movement detected')}</span>
                        </div>
                        <div class="detail">
                            Price: ${alert.get('price_at_trade', 'N/A')} • 
                            10d return: {alert.get('return_10d', 'N/A')}% • 
                            20d return: {alert.get('return_20d', 'N/A')}%
                        </div>
                    </div>
                """
        else:
            html += '<div class="section-empty">No against-market trades detected</div>'
        html += "</div></div>"
        
        # Section: Pre-Earnings Trades
        pre_earnings_alerts = alert_groups['PRE_EARNINGS']
        html += f"""
            <div class="section">
                <div class="section-header" style="background: #5a67d8;">
                    📅 Pre-Earnings Trades
                    <span class="count">{len(pre_earnings_alerts)}</span>
                </div>
                <div class="section-body">
        """
        if pre_earnings_alerts:
            for alert in pre_earnings_alerts:
                trade_class = 'trade-buy' if alert.get('trade_type', '').lower() in ['purchase', 'buy'] else 'trade-sell'
                html += f"""
                    <div class="alert-row">
                        <span class="priority-badge priority-{alert.get('priority', 'MEDIUM')}">{alert.get('priority', 'MEDIUM')}</span>
                        <span class="ticker">{alert.get('ticker', 'N/A')}</span>
                        <span class="{trade_class}" style="margin-left: 10px; font-weight: bold;">
                            {alert.get('trade_type', 'N/A').upper()}
                        </span>
                        <div class="detail">
                            <span class="politician">{alert.get('politician', 'Unknown')}</span> • 
                            Trade: {alert.get('trade_date', 'N/A')}
                        </div>
                        <div class="detail">
                            <span class="highlight">⚠️ {alert.get('days_before_earnings', '?')} days before earnings ({alert.get('earnings_date', 'N/A')})</span>
                        </div>
                    </div>
                """
        else:
            html += '<div class="section-empty">No pre-earnings trades detected</div>'
        html += "</div></div>"
        
        # Section: Clusters
        cluster_alerts = alert_groups['CLUSTER']
        html += f"""
            <div class="section">
                <div class="section-header" style="background: #2b6cb0;">
                    👥 Trading Clusters
                    <span class="count">{len(cluster_alerts)}</span>
                </div>
                <div class="section-body">
        """
        if cluster_alerts:
            for alert in cluster_alerts:
                bipartisan_badge = '<span style="background:#e9d5ff;color:#6b21a8;padding:2px 6px;border-radius:3px;font-size:11px;margin-left:8px;">BIPARTISAN</span>' if alert.get('bipartisan') else ''
                html += f"""
                    <div class="alert-row">
                        <span class="priority-badge priority-{alert.get('priority', 'MEDIUM')}">{alert.get('priority', 'MEDIUM')}</span>
                        <span class="ticker">{alert.get('ticker', 'N/A')}</span>
                        {bipartisan_badge}
                        <div class="detail">
                            {alert.get('politician_count', 0)} politicians trading same stock •
                            R: {alert.get('party_breakdown', {}).get('Republican', 0)} / D: {alert.get('party_breakdown', {}).get('Democrat', 0)}
                        </div>
                        <div class="detail">
                            Politicians: {', '.join(alert.get('politicians', [])[:5])}{'...' if len(alert.get('politicians', [])) > 5 else ''}
                        </div>
                    </div>
                """
        else:
            html += '<div class="section-empty">No trading clusters detected</div>'
        html += "</div></div>"
        
        # Section: Large Trades
        large_alerts = alert_groups['LARGE_TRADE']
        html += f"""
            <div class="section">
                <div class="section-header" style="background: #38a169;">
                    💰 Large Trades (>$250K)
                    <span class="count">{len(large_alerts)}</span>
                </div>
                <div class="section-body">
        """
        if large_alerts:
            for alert in large_alerts:
                est_amount = alert.get('estimated_amount', 0)
                if est_amount >= 1000000:
                    amount_display = f"${est_amount/1000000:.1f}M"
                else:
                    amount_display = f"${est_amount:,.0f}"
                html += f"""
                    <div class="alert-row">
                        <span class="priority-badge priority-{alert.get('priority', 'MEDIUM')}">{alert.get('priority', 'MEDIUM')}</span>
                        <span class="ticker">{alert.get('ticker', 'N/A')}</span>
                        <span style="color:#38a169;font-weight:bold;margin-left:10px;">{amount_display}</span>
                        <div class="detail">
                            <span class="politician">{alert.get('politician', 'Unknown')}</span> • 
                            {alert.get('amount_range', 'Unknown')}
                        </div>
                    </div>
                """
        else:
            html += '<div class="section-empty">No large trades detected</div>'
        html += "</div></div>"
        
        # Section: Committee Relevant
        committee_alerts = alert_groups['COMMITTEE_RELEVANT']
        html += f"""
            <div class="section">
                <div class="section-header" style="background: #805ad5;">
                    🏛️ Committee-Relevant Trades
                    <span class="count">{len(committee_alerts)}</span>
                </div>
                <div class="section-body">
        """
        if committee_alerts:
            for alert in committee_alerts:
                html += f"""
                    <div class="alert-row">
                        <span class="priority-badge priority-{alert.get('priority', 'MEDIUM')}">{alert.get('priority', 'MEDIUM')}</span>
                        <span class="ticker">{alert.get('ticker', 'N/A')}</span>
                        <span style="color:#805ad5;margin-left:10px;">({alert.get('sector', 'Unknown')} sector)</span>
                        <div class="detail">
                            <span class="politician">{alert.get('politician', 'Unknown')}</span> • 
                            <span class="highlight">{alert.get('committee', 'Unknown Committee')}</span>
                        </div>
                    </div>
                """
        else:
            html += '<div class="section-empty">No committee-relevant trades detected</div>'
        html += "</div></div>"
        
        # Section: Sector Surges
        sector_alerts = alert_groups['SECTOR_SURGE']
        html += f"""
            <div class="section">
                <div class="section-header" style="background: #319795;">
                    📈 Sector Surges
                    <span class="count">{len(sector_alerts)}</span>
                </div>
                <div class="section-body">
        """
        if sector_alerts:
            for alert in sector_alerts:
                bipartisan_badge = '<span style="background:#e9d5ff;color:#6b21a8;padding:2px 6px;border-radius:3px;font-size:11px;margin-left:8px;">BIPARTISAN</span>' if alert.get('bipartisan') else ''
                html += f"""
                    <div class="alert-row">
                        <span class="priority-badge priority-{alert.get('priority', 'MEDIUM')}">{alert.get('priority', 'MEDIUM')}</span>
                        <span class="ticker">{alert.get('sector', 'N/A')} Sector</span>
                        {bipartisan_badge}
                        <div class="detail">
                            {alert.get('politician_count', 0)} politicians • 
                            Tickers: {', '.join(alert.get('tickers', [])[:5])}
                        </div>
                    </div>
                """
        else:
            html += '<div class="section-empty">No sector surges detected</div>'
        html += "</div></div>"
        
        # Section: Repeat Buyers
        repeat_alerts = alert_groups['REPEAT_BUYER']
        html += f"""
            <div class="section">
                <div class="section-header" style="background: #718096;">
                    🔄 Repeat Buyers
                    <span class="count">{len(repeat_alerts)}</span>
                </div>
                <div class="section-body">
        """
        if repeat_alerts:
            for alert in repeat_alerts:
                html += f"""
                    <div class="alert-row">
                        <span class="priority-badge priority-{alert.get('priority', 'MEDIUM')}">{alert.get('priority', 'MEDIUM')}</span>
                        <span class="ticker">{alert.get('ticker', 'N/A')}</span>
                        <div class="detail">
                            <span class="politician">{alert.get('politician', 'Unknown')}</span> • 
                            {alert.get('total_purchases', 0)} total purchases of this stock
                        </div>
                    </div>
                """
        else:
            html += '<div class="section-empty">No repeat buyers detected</div>'
        html += "</div></div>"
        
        # Section: New Positions (collapsed summary only)
        new_position_alerts = alert_groups['NEW_POSITION']
        html += f"""
            <div class="section">
                <div class="section-header" style="background: #a0aec0;">
                    🆕 New Positions
                    <span class="count">{len(new_position_alerts)}</span>
                </div>
                <div class="section-body">
        """
        if new_position_alerts:
            # Just show summary for new positions (usually many)
            if len(new_position_alerts) <= 5:
                for alert in new_position_alerts:
                    html += f"""
                        <div class="alert-row">
                            <span class="priority-badge priority-LOW">LOW</span>
                            <span class="ticker">{alert.get('ticker', 'N/A')}</span>
                            <div class="detail">
                                <span class="politician">{alert.get('politician', 'Unknown')}</span> • First trade in this stock
                            </div>
                        </div>
                    """
            else:
                # Summarize
                tickers = list(set(a.get('ticker', 'N/A') for a in new_position_alerts))
                politicians = list(set(a.get('politician', 'Unknown') for a in new_position_alerts))
                html += f"""
                    <div class="alert-row">
                        <div class="detail">
                            {len(new_position_alerts)} new positions opened by {len(politicians)} politicians
                        </div>
                        <div class="detail">
                            Tickers: {', '.join(tickers[:10])}{'...' if len(tickers) > 10 else ''}
                        </div>
                    </div>
                """
        else:
            html += '<div class="section-empty">No new positions detected</div>'
        html += "</div></div>"
    
    # Footer
    html += """
        </div>
        
        <div class="footer">
            <p><strong>Congressional Trading Tracker</strong></p>
            <p>Data sourced from official House and Senate financial disclosures via Financial Modeling Prep API</p>
            <p style="margin-top: 10px; font-size: 11px;">
                Alert Types: 🤝 Bipartisan • 👑 Leadership • 📉 Against-Market • 📅 Pre-Earnings • 👥 Clusters • 💰 Large Trades • 🏛️ Committee • 📈 Sector Surge • 🔄 Repeat • 🆕 New Position
            </p>
        </div>
    </body>
    </html>
    """
    
    return html


def format_analysis_report_text(results: Dict) -> str:
    """Format the full analysis report as plain text."""
    summary = results.get('summary', {})
    alerts = results.get('alerts', [])
    
    lines = []
    lines.append("=" * 70)
    lines.append("🏛️ CONGRESSIONAL TRADING ANALYSIS REPORT")
    lines.append(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"   {results.get('transaction_count', 0)} transactions analyzed")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"SUMMARY:")
    lines.append(f"  Total Alerts: {summary.get('total_alerts', 0)}")
    lines.append(f"  HIGH Priority: {summary.get('high_priority', 0)}")
    lines.append(f"  MEDIUM Priority: {summary.get('medium_priority', 0)}")
    lines.append(f"  LOW Priority: {summary.get('low_priority', 0)}")
    lines.append("")
    lines.append(f"BY TYPE:")
    lines.append(f"  Bipartisan: {summary.get('bipartisan', 0)}")
    lines.append(f"  Clusters: {summary.get('clusters', 0)}")
    lines.append(f"  Committee-Relevant: {summary.get('committee_relevant', 0)}")
    lines.append(f"  Leadership: {summary.get('leadership', 0)}")
    lines.append(f"  Large Trades: {summary.get('large_trades', 0)}")
    lines.append(f"  Sector Surges: {summary.get('sector_surges', 0)}")
    lines.append(f"  Repeat Buyers: {summary.get('repeat_buyers', 0)}")
    lines.append(f"  New Positions: {summary.get('new_positions', 0)}")
    lines.append(f"  Pre-Earnings: {summary.get('pre_earnings', 0)}")
    lines.append(f"  Against-Market: {summary.get('against_market', 0)}")
    lines.append("")
    lines.append("-" * 70)
    
    # Group by priority for text output
    high_priority = [a for a in alerts if a.get('priority') == 'HIGH']
    medium_priority = [a for a in alerts if a.get('priority') == 'MEDIUM']
    
    if high_priority:
        lines.append("")
        lines.append("🔴 HIGH PRIORITY ALERTS:")
        lines.append("-" * 70)
        for alert in high_priority:
            alert_type = alert.get('type', 'UNKNOWN')
            ticker = alert.get('ticker', 'N/A')
            politician = alert.get('politician', alert.get('politicians', ['N/A'])[0] if isinstance(alert.get('politicians'), list) else 'N/A')
            
            if alert_type == 'BIPARTISAN':
                lines.append(f"  🤝 BIPARTISAN: {ticker}")
                lines.append(f"     R: {', '.join(alert.get('republican_politicians', [])[:3])}")
                lines.append(f"     D: {', '.join(alert.get('democrat_politicians', [])[:3])}")
            elif alert_type == 'LEADERSHIP_TRADE':
                lines.append(f"  👑 LEADERSHIP: {politician} ({alert.get('position', 'Leader')})")
                lines.append(f"     {alert.get('trade_type', 'N/A').upper()} {ticker} - {alert.get('amount_range', 'N/A')}")
            elif alert_type == 'AGAINST_MARKET':
                lines.append(f"  📉 AGAINST-MARKET: {politician}")
                lines.append(f"     {ticker} - {alert.get('reason', 'Price movement detected')}")
            elif alert_type == 'PRE_EARNINGS':
                lines.append(f"  📅 PRE-EARNINGS: {politician}")
                lines.append(f"     {ticker} - {alert.get('days_before_earnings', '?')} days before earnings")
            elif alert_type == 'CLUSTER':
                lines.append(f"  👥 CLUSTER: {ticker} - {alert.get('politician_count', 0)} politicians")
                lines.append(f"     Bipartisan: {'Yes' if alert.get('bipartisan') else 'No'}")
            else:
                lines.append(f"  {alert_type}: {ticker} - {politician}")
            lines.append("")
    
    if medium_priority:
        lines.append("")
        lines.append("🟠 MEDIUM PRIORITY ALERTS:")
        lines.append("-" * 70)
        for alert in medium_priority[:10]:  # Limit to 10 for text
            alert_type = alert.get('type', 'UNKNOWN')
            ticker = alert.get('ticker', 'N/A')
            politician = alert.get('politician', 'N/A')
            lines.append(f"  {alert_type}: {ticker} - {politician}")
        if len(medium_priority) > 10:
            lines.append(f"  ... and {len(medium_priority) - 10} more")
    
    lines.append("")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def send_analysis_report(results: Dict, dry_run: bool = False) -> bool:
    """
    Send the full daily analysis report email.
    
    Args:
        results: Output from analyzer.run_all_analysis()
        dry_run: If True, print instead of sending
    """
    summary = results.get('summary', {})
    
    # Build subject line
    high_count = summary.get('high_priority', 0)
    total_count = summary.get('total_alerts', 0)
    bipartisan_count = summary.get('bipartisan', 0)
    
    if bipartisan_count > 0:
        subject = f"🤝 Congress Tracker: {bipartisan_count} Bipartisan Alert{'s' if bipartisan_count != 1 else ''}"
        if high_count > bipartisan_count:
            subject += f" + {high_count - bipartisan_count} High Priority"
    elif high_count > 0:
        subject = f"🚨 Congress Tracker: {high_count} High Priority Alert{'s' if high_count != 1 else ''}"
    elif total_count > 0:
        subject = f"📊 Congress Tracker: {total_count} Alert{'s' if total_count != 1 else ''} Detected"
    else:
        subject = f"✅ Congress Tracker: No Alerts - {datetime.now().strftime('%Y-%m-%d')}"
    
    # Generate content
    text_body = format_analysis_report_text(results)
    html_body = format_analysis_report_html(results)
    
    if dry_run:
        print(f"\n{'='*70}")
        print("DRY RUN - Would send email:")
        print(f"{'='*70}")
        print(f"Subject: {subject}")
        print(f"To: {config.EMAIL_RECIPIENT}")
        print(f"\n{text_body}")
        return True
    
    return send_email(subject, text_body, html_body)


def send_test_email() -> bool:
    """Send a test email to verify configuration."""
    subject = "🧪 Congress Tracker - Test Email"
    
    text_body = f"""
This is a test email from the Congressional Trading Tracker.

If you received this, your email configuration is working correctly!

Configuration:
  SMTP Server: {config.SMTP_SERVER}
  Sender: {config.EMAIL_SENDER}
  Recipient: {config.EMAIL_RECIPIENT}
  Alert Threshold: {config.ALERT_THRESHOLD}
  Cluster Window: {config.CLUSTER_WINDOW_DAYS} days

The tracker will send alerts when:
  • 3+ politicians trade the same stock within {config.CLUSTER_WINDOW_DAYS} days
  • Additional signals like bipartisan trades, committee relevance, etc.
  • Total score meets threshold of {config.ALERT_THRESHOLD}

Happy tracking! 🏛️
"""
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%); color: white; padding: 20px; border-radius: 8px;">
            <h1 style="margin: 0;">🧪 Test Email Successful!</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Congressional Trading Tracker</p>
        </div>
        
        <div style="padding: 20px;">
            <p>Your email configuration is working correctly.</p>
            
            <div style="background: #f0fff4; border: 1px solid #9ae6b4; border-radius: 8px; padding: 15px; margin: 20px 0;">
                <strong>✅ Configuration Verified</strong>
                <ul style="margin: 10px 0 0 0;">
                    <li>SMTP Server: {config.SMTP_SERVER}</li>
                    <li>Recipient: {config.EMAIL_RECIPIENT}</li>
                </ul>
            </div>
            
            <h3>Alert Settings:</h3>
            <ul>
                <li>Minimum cluster size: {config.MIN_CLUSTER_SIZE} politicians</li>
                <li>Cluster window: {config.CLUSTER_WINDOW_DAYS} days</li>
                <li>Alert threshold score: {config.ALERT_THRESHOLD}</li>
            </ul>
            
            <p style="color: #718096; font-size: 14px; margin-top: 30px;">
                You'll receive instant alerts when congressional trading patterns are detected.
            </p>
        </div>
    </body>
    </html>
    """
    
    return send_email(subject, text_body, html_body)


if __name__ == "__main__":
    print("Testing email configuration...")
    print(f"Sender: {config.EMAIL_SENDER}")
    print(f"Recipient: {config.EMAIL_RECIPIENT}")
    
    if "your_email" in config.EMAIL_SENDER or "your_app_password" in config.EMAIL_PASSWORD:
        print("\n⚠️  Email credentials not configured!")
        print("Edit config.py with your Gmail and App Password.")
    else:
        print("\nSending test email...")
        if send_test_email():
            print("✅ Test email sent! Check your inbox.")
        else:
            print("❌ Failed to send test email.")
