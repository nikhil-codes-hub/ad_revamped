import streamlit as st
import os
import pandas as pd

def render_custom_table(df, long_text_cols=None, css_rel_path=None):
    """
    Renders a styled HTML table in Streamlit, with optional long-text handling and CSS injection.
    Args:
        df (pd.DataFrame): Data to display
        long_text_cols (list): Columns to use 'pre-wrap' for long text
        css_rel_path (str): Relative path to the CSS file (from the calling file)
    """
    if df.empty:
        st.markdown(":red[No data found.]", unsafe_allow_html=True)
        return
    df = df.reset_index(drop=True)
    
    # Inject CSS if path given
    if css_rel_path:
        css_path = os.path.abspath(css_rel_path)
        try:
            with open(css_path, "r") as f:
                table_css = f.read()
            st.markdown(f"<style>{table_css}</style>", unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"Could not load table CSS: {e}")
    
    # Build HTML table
    if long_text_cols is None:
        long_text_cols = []
    
    # Create a DataFrame for display with properly escaped XML content
    display_df = df.copy()
    # Style the Verified column
    if 'Verified' in display_df.columns:
        def style_verified(val):
            if str(val).strip().lower() == 'yes':
                return '<span class="verified-yes">Yes</span>'
            elif str(val).strip().lower() == 'no':
                return '<span class="verified-no">No</span>'
            return val
        display_df['Verified'] = display_df['Verified'].apply(style_verified)
    # Escape < and > in all columns except the 'Verified' column (already HTML)
    for col in display_df.columns:
        # For XML example column, wrap in <pre> and escape
        if col.lower() == 'example':
            display_df[col] = display_df[col].apply(
                lambda x: f'<pre class="xml-example">{str(x).replace("<", "&lt;").replace(">", "&gt;")}</pre>'
            )
        elif col != 'Verified':  # Don't escape HTML in Verified column
            display_df[col] = display_df[col].apply(lambda x: str(x).replace('<', '&lt;').replace('>', '&gt;'))

    # Build the HTML table, applying .pre-wrap class to long_text_cols
    def _add_pre_wrap_to_col(html, colnames):
        # Add .pre-wrap class to <td> and <th> for specified columns
        for col in colnames:
            html = html.replace(f'<th>{col}</th>', f'<th class="pre-wrap">{col}</th>')
        # Find column indices
        if not colnames:
            return html
        import re
        # Get header order
        header_match = re.search(r'<thead>.*?</thead>', html, re.DOTALL)
        if not header_match:
            return html
        header_html = header_match.group(0)
        headers = [h.strip() for h in re.findall(r'<th.*?>(.*?)</th>', header_html)]
        indices = [i for i, h in enumerate(headers) if h in colnames]
        if not indices:
            return html
        # Add .pre-wrap to <td> for those columns
        def repl_td(match):
            tds = re.findall(r'<td.*?>.*?</td>', match.group(0))
            for i in indices:
                if i < len(tds):
                    tds[i] = tds[i].replace('<td', '<td class="pre-wrap"', 1)
            return '<tr>' + ''.join(tds) + '</tr>'
        html = re.sub(r'<tr>(.*?)</tr>', repl_td, html, flags=re.DOTALL)
        return html

    # Generate HTML manually to ensure proper styling
    def generate_table_html(df, long_text_cols):
        # Header with inline styles to ensure white text - most aggressive approach
        header_style = (
            'background-color: #3b82f6 !important; '
            'background: #3b82f6 !important; '
            'color: #ffffff !important; '
            'color: white !important; '
            'font-weight: 600 !important; '
            'text-transform: uppercase !important; '
            'letter-spacing: 0.5px !important; '
            'font-size: 0.875rem !important; '
            'padding: 12px 16px !important; '
            'border: none !important; '
            'text-align: left !important; '
            'text-shadow: none !important; '
            '-webkit-text-fill-color: white !important; '
            'fill: white !important;'
        )
        
        # Table structure
        html_parts = ['<table style="width: 100%; border-collapse: collapse; background: white;">']
        
        # Generate header
        html_parts.append('<thead>')
        html_parts.append('<tr>')
        for col in df.columns:
            col_class = ' class="pre-wrap"' if col in long_text_cols else ''
            html_parts.append(f'<th{col_class} style="{header_style}">{col}</th>')
        html_parts.append('</tr>')
        html_parts.append('</thead>')
        
        # Generate body
        html_parts.append('<tbody>')
        for _, row in df.iterrows():
            html_parts.append('<tr>')
            for i, (col, value) in enumerate(row.items()):
                cell_class = ' class="pre-wrap"' if col in long_text_cols else ''
                cell_style = (
                    'padding: 12px 16px !important; '
                    'border-bottom: 1px solid #f3f4f6 !important; '
                    'vertical-align: top !important; '
                    'word-wrap: break-word !important; '
                    'color: #1f2937 !important;'
                )
                if col in long_text_cols:
                    cell_style += (
                        'white-space: pre-wrap !important; '
                        'word-break: break-word !important; '
                        'overflow-wrap: break-word !important; '
                        'max-width: 0 !important;'
                    )
                html_parts.append(f'<td{cell_class} style="{cell_style}">{value}</td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody>')
        html_parts.append('</table>')
        
        return ''.join(html_parts)
    
    html = generate_table_html(display_df, long_text_cols)
    # Add custom wrapper and styling
    html = f'<div class="custom-table-wrapper">{html}</div>'
    # Add custom CSS enhancements (minimal since we use inline styles for critical styling)
    custom_css = '''
    /* Enhanced word-wrapping for table cells */
    .custom-table-wrapper td.pre-wrap {
        white-space: pre-wrap !important;
        line-height: 1.6 !important;
        min-width: 120px !important;
        overflow: visible !important;
    }
    
    /* Better spacing for wrapped content */
    .custom-table-wrapper table {
        table-layout: fixed !important;
        width: 100% !important;
    }
    
    /* Hover effect for table rows */
    .custom-table-wrapper tbody tr:hover td {
        background: rgba(59, 130, 246, 0.05) !important;
        transition: background-color 0.2s ease !important;
    }
    
    /* Ensure header text remains white even with Streamlit overrides */
    .custom-table-wrapper th {
        background: #3b82f6 !important;
        color: white !important;
    }
    .xml-example {
        font-family: "Fira Mono", "Consolas", "Menlo", "Monaco", "Courier New", monospace;
        background: #f8f8fa;
        color: #222;
        font-size: 0.85em;
        white-space: pre-wrap !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        padding: 0.75em;
        border-radius: 6px;
        margin: 0;
        display: block;
        max-width: 100%;
        overflow-x: auto;
        line-height: 1.4;
        border: 1px solid #e2e8f0;
        max-height: 200px;
        overflow-y: auto;
    }
    .verified-yes {
        background-color: #d4edda;
        color: #155724;
        font-weight: bold;
        padding: 3px 8px;
        border-radius: 4px;
        display: inline-block;
        text-align: center;
    }
    .verified-no {
        background-color: #f8d7da;
        color: #721c24;
        font-weight: bold;
        padding: 3px 8px;
        border-radius: 4px;
        display: inline-block;
        text-align: center;
    }
    '''
    # Inject CSS
    st.markdown(f'<style>{custom_css}</style>', unsafe_allow_html=True)
    # Display the table
    st.markdown(html, unsafe_allow_html=True)
