import altair as alt

@alt.theme.register('agro_dark_terminal', enable=True)
def _altair_dark_theme_terminal():
    return alt.theme.ThemeConfig(
        {
            'background': 'transparent',
            'view': {'stroke': 'transparent'},
            'axis': {
                'domainColor': '#30363d',
                'gridColor': '#21262d',
                'tickColor': '#30363d',
                'labelColor': '#8b949e',
                'titleColor': '#8b949e',
                'labelFont': 'Roboto Mono, monospace',
                'titleFont': 'Inter, sans-serif',
                'titleFontWeight': 600,
                'labelFontSize': 10,
                'titleFontSize': 12
            },
            'legend': {
                'labelColor': '#8b949e',
                'titleColor': '#8b949e',
                'labelFont': 'Roboto Mono, monospace',
                'titleFont': 'Inter, sans-serif'
            },
            'title': {
                'color': '#c9d1d9',
                'font': 'Inter, sans-serif',
                'fontSize': 14,
                'fontWeight': 600
            }
        }
    )

@alt.theme.register('agro_glass_light', enable=True)
def _altair_glass_theme_light():
    return alt.theme.ThemeConfig(
        {
            'background': 'transparent',
            'view': {'stroke': 'transparent'},
            'axis': {
                'domainColor': '#e5e7eb',
                'gridColor': '#f3f4f6',
                'tickColor': '#e5e7eb',
                'labelColor': '#6b7280',
                'titleColor': '#4b5563',
                'labelFont': 'Inter, sans-serif',
                'titleFont': 'Inter, sans-serif',
                'titleFontWeight': 600,
                'labelFontSize': 11,
                'titleFontSize': 12
            },
            'legend': {
                'labelColor': '#4b5563',
                'titleColor': '#374151',
                'labelFont': 'Inter, sans-serif',
                'titleFont': 'Inter, sans-serif'
            },
            'title': {
                'color': '#111827',
                'font': 'Inter, sans-serif',
                'fontSize': 15,
                'fontWeight': 700
            }
        }
    )
