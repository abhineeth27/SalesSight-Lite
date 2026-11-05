import { useMemo, useRef, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
})
const integer = new Intl.NumberFormat('en-IN')
const shortInr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  notation: 'compact',
  maximumFractionDigits: 1,
})

function readError(payload, fallback) {
  const detail = payload?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) {
    const examples = (detail.errors || [])
      .map((item) => {
        if (item.example_rows?.length) return `${item.issue} (rows ${item.example_rows.join(', ')})`
        if (item.detail) return `${item.issue}: ${item.detail}`
        return item.issue
      })
      .filter(Boolean)
    return [detail.message, ...examples].join(' ')
  }
  return fallback
}

async function parseResponse(response, fallback) {
  let payload = null
  try {
    payload = await response.json()
  } catch {
    // Use the friendly fallback below when a proxy/server returns non-JSON.
  }
  if (!response.ok) throw new Error(readError(payload, fallback))
  return payload
}

function RevenueTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>
      {payload
        .filter((item) => item.value !== null && item.value !== undefined)
        .map((item) => (
          <span key={item.dataKey} style={{ color: item.color }}>
            {item.name}: {inr.format(item.value)}
          </span>
        ))}
    </div>
  )
}

function EmptyState() {
  return (
    <section className="empty-state" aria-live="polite">
      <div className="empty-icon">↗</div>
      <h2>Your sales story starts here</h2>
      <p>Load the synthetic demo or upload a CSV to calculate KPIs, charts, and a seven-day forecast.</p>
    </section>
  )
}

function App() {
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [success, setSuccess] = useState('')
  const [insight, setInsight] = useState('')
  const [insightLoading, setInsightLoading] = useState(false)
  const [insightError, setInsightError] = useState('')
  const uploadSequence = useRef(0)
  const insightSequence = useRef(0)
  const uploadController = useRef(null)
  const insightController = useRef(null)
  const fileInput = useRef(null)

  const forecastChartData = useMemo(() => {
    if (!analysis) return []
    const rows = analysis.daily_revenue.map((item) => ({
      date: item.date,
      historical: item.revenue,
      forecast: null,
    }))
    if (analysis.forecast.available && rows.length) {
      rows[rows.length - 1].forecast = rows[rows.length - 1].historical
      for (const item of analysis.forecast.predictions) {
        rows.push({ date: item.date, historical: null, forecast: item.predicted_revenue })
      }
    }
    return rows
  }, [analysis])

  async function runAnalysis(getFile, label) {
    const requestNumber = ++uploadSequence.current
    ++insightSequence.current
    uploadController.current?.abort()
    insightController.current?.abort()
    const controller = new AbortController()
    uploadController.current = controller

    setLoading(true)
    setAnalysis(null)
    setInsight('')
    setInsightError('')
    setLoadError('')
    setSuccess('')

    try {
      const file = await getFile(controller.signal)
      if (requestNumber !== uploadSequence.current) return
      const form = new FormData()
      form.append('file', file, file.name)
      const response = await fetch('/api/analyze', {
        method: 'POST',
        body: form,
        signal: controller.signal,
      })
      const payload = await parseResponse(response, 'The sales file could not be analyzed.')
      if (requestNumber !== uploadSequence.current) return
      setAnalysis(payload)
      setSuccess(`${label} loaded successfully.`)
    } catch (error) {
      if (error.name !== 'AbortError' && requestNumber === uploadSequence.current) {
        setLoadError(error.message || 'The sales file could not be analyzed.')
      }
    } finally {
      if (requestNumber === uploadSequence.current) setLoading(false)
    }
  }

  function handleUpload(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    runAnalysis(async () => file, file.name)
  }

  function loadDemo() {
    runAnalysis(async (signal) => {
      const response = await fetch('/sample_sales.csv', { signal, cache: 'no-store' })
      if (!response.ok) throw new Error('The bundled demo CSV could not be loaded.')
      const blob = await response.blob()
      return new File([blob], 'salessight_synthetic_demo.csv', { type: 'text/csv' })
    }, 'Synthetic demo data')
  }

  async function generateInsights() {
    if (!analysis || insight || insightLoading) return
    const analysisId = analysis.analysis_id
    const requestNumber = ++insightSequence.current
    insightController.current?.abort()
    const controller = new AbortController()
    insightController.current = controller
    setInsightLoading(true)
    setInsightError('')

    try {
      const response = await fetch('/api/insights', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ analysis_id: analysisId }),
        signal: controller.signal,
      })
      const payload = await parseResponse(response, 'AI insights could not be generated.')
      if (
        requestNumber === insightSequence.current &&
        payload.analysis_id === analysisId &&
        analysis.analysis_id === analysisId
      ) {
        setInsight(payload.insight)
      }
    } catch (error) {
      if (error.name !== 'AbortError' && requestNumber === insightSequence.current) {
        setInsightError(error.message || 'AI insights could not be generated.')
      }
    } finally {
      if (requestNumber === insightSequence.current) setInsightLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <div className="eyebrow">SALES ANALYTICS • COLLEGE PROJECT</div>
          <h1>SalesSight <span>Lite</span></h1>
          <p>Turn a simple sales CSV into clear business KPIs, a basic trend forecast, and optional AI explanations.</p>
        </div>
        <div className="hero-mark" aria-hidden="true">
          <span></span><span></span><span></span><span></span>
        </div>
      </header>

      <main>
        <section className="control-panel" aria-labelledby="data-heading">
          <div className="control-copy">
            <h2 id="data-heading">Choose sales data</h2>
            <p>
              Required columns: <code>date, order_id, product, quantity, unit_price</code>.
              Dates must use YYYY-MM-DD; limit 5 MB.
            </p>
          </div>
          <div className="controls">
            <input
              ref={fileInput}
              type="file"
              accept=".csv,text/csv"
              onChange={handleUpload}
              className="visually-hidden"
              id="csv-upload"
            />
            <button className="button primary" onClick={() => fileInput.current?.click()} disabled={loading}>
              Upload CSV
            </button>
            <button className="button secondary" onClick={loadDemo} disabled={loading}>
              Load Demo Data
            </button>
            <a className="button ghost" href="/sample_sales.csv" download="salessight_synthetic_demo.csv">
              Download Sample CSV
            </a>
          </div>
        </section>

        {loading && (
          <div className="status loading" role="status">
            <span className="spinner" /> Validating rows and calculating the dashboard…
          </div>
        )}
        {loadError && <div className="status error" role="alert">{loadError}</div>}
        {success && analysis && <div className="status success" role="status">{success}</div>}

        {!analysis && !loading && <EmptyState />}

        {analysis && (
          <div className="dashboard">
            <section className="dataset-summary">
              <div>
                <span className="meta-label">CURRENT DATASET</span>
                <strong>{analysis.filename}</strong>
              </div>
              <div>
                <span className="meta-label">DATE RANGE</span>
                <strong>{analysis.date_start} → {analysis.date_end}</strong>
              </div>
              <div>
                <span className="meta-label">COVERAGE</span>
                <strong>{integer.format(analysis.row_count)} lines • {analysis.calendar_days} days</strong>
              </div>
            </section>

            <section className="kpi-grid" aria-label="Key performance indicators">
              <article className="kpi-card">
                <span>Total revenue</span>
                <strong>{inr.format(analysis.kpis.total_revenue)}</strong>
                <small>Quantity × unit price</small>
              </article>
              <article className="kpi-card">
                <span>Total orders</span>
                <strong>{integer.format(analysis.kpis.total_orders)}</strong>
                <small>Unique order IDs</small>
              </article>
              <article className="kpi-card">
                <span>Average order value</span>
                <strong>{inr.format(analysis.kpis.average_order_value)}</strong>
                <small>Revenue per order</small>
              </article>
              <article className="kpi-card">
                <span>Units sold</span>
                <strong>{integer.format(analysis.kpis.units_sold)}</strong>
                <small>Total quantity</small>
              </article>
            </section>

            <section className="chart-grid">
              <article className="panel chart-panel wide">
                <div className="panel-heading">
                  <div>
                    <span className="section-kicker">HISTORICAL</span>
                    <h2>Daily revenue</h2>
                  </div>
                  <span className="pill">INR</span>
                </div>
                <div className="chart-area">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={analysis.daily_revenue} margin={{ top: 8, right: 12, left: 8, bottom: 0 }}>
                      <CartesianGrid stroke="#e7ebe9" strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="date" minTickGap={35} tick={{ fontSize: 12 }} />
                      <YAxis tickFormatter={(value) => shortInr.format(value)} width={72} tick={{ fontSize: 12 }} />
                      <Tooltip content={<RevenueTooltip />} />
                      <Line type="monotone" dataKey="revenue" name="Revenue" stroke="#1f6f68" strokeWidth={2.4} dot={false} activeDot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </article>

              <article className="panel chart-panel">
                <div className="panel-heading">
                  <div>
                    <span className="section-kicker">PRODUCT MIX</span>
                    <h2>Top five products</h2>
                  </div>
                </div>
                <div className="chart-area">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={analysis.top_products} layout="vertical" margin={{ top: 6, right: 20, left: 14, bottom: 0 }}>
                      <CartesianGrid stroke="#e7ebe9" strokeDasharray="3 3" horizontal={false} />
                      <XAxis type="number" tickFormatter={(value) => shortInr.format(value)} tick={{ fontSize: 11 }} />
                      <YAxis type="category" dataKey="product" width={112} tick={{ fontSize: 12 }} />
                      <Tooltip content={<RevenueTooltip />} />
                      <Bar dataKey="revenue" name="Revenue" fill="#1f6f68" radius={[0, 5, 5, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </article>
            </section>

            <section className="panel forecast-panel">
              <div className="panel-heading forecast-heading">
                <div>
                  <span className="section-kicker">LINEAR REGRESSION</span>
                  <h2>Basic trend forecast</h2>
                  <p>{analysis.forecast.assumption}</p>
                </div>
                {analysis.forecast.available && analysis.forecast.evaluation && (
                  <div className="metric-callout">
                    <span>Holdout MAE</span>
                    <strong>{inr.format(analysis.forecast.evaluation.mae)}</strong>
                    <small>Lower is better</small>
                  </div>
                )}
              </div>

              {!analysis.forecast.available ? (
                <div className="forecast-unavailable">
                  <strong>Forecast unavailable</strong>
                  <p>{analysis.forecast.reason}</p>
                  <p>{analysis.forecast.limitation}</p>
                </div>
              ) : (
                <>
                  <div className="forecast-layout">
                    <div className="chart-area forecast-chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={forecastChartData} margin={{ top: 8, right: 12, left: 8, bottom: 0 }}>
                          <CartesianGrid stroke="#e7ebe9" strokeDasharray="3 3" vertical={false} />
                          <XAxis dataKey="date" minTickGap={38} tick={{ fontSize: 12 }} />
                          <YAxis tickFormatter={(value) => shortInr.format(value)} width={72} tick={{ fontSize: 12 }} />
                          <Tooltip content={<RevenueTooltip />} />
                          <Legend />
                          <Line type="monotone" dataKey="historical" name="Historical revenue" stroke="#1f6f68" strokeWidth={2.2} dot={false} />
                          <Line type="monotone" dataKey="forecast" name="7-day prediction" stroke="#c57928" strokeWidth={2.4} strokeDasharray="7 5" dot={{ r: 3 }} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="forecast-table-wrap">
                      <table>
                        <thead><tr><th>Date</th><th>Predicted revenue</th></tr></thead>
                        <tbody>
                          {analysis.forecast.predictions.map((item) => (
                            <tr key={item.date}><td>{item.date}</td><td>{inr.format(item.predicted_revenue)}</td></tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div className="model-note">
                    <p>{analysis.forecast.evaluation.explanation}</p>
                    <p>
                      Mean baseline MAE: <strong>{inr.format(analysis.forecast.evaluation.baseline_mae)}</strong>.{' '}
                      The trend model performed {analysis.forecast.evaluation.model_better_than_baseline ? 'better' : 'worse'} on this holdout.
                    </p>
                    <p><strong>Limitation:</strong> {analysis.forecast.limitation}</p>
                  </div>
                </>
              )}
            </section>

            <section className="panel insight-panel">
              <div className="insight-copy">
                <span className="section-kicker">OPTIONAL • GEMINI</span>
                <h2>AI insights</h2>
                <p>
                  Gemini receives only a compact server-calculated summary—not the CSV, order IDs, or your API key.
                  It explains the numbers; it never calculates them.
                </p>
              </div>
              <button
                className="button primary insight-button"
                onClick={generateInsights}
                disabled={insightLoading || Boolean(insight)}
              >
                {insightLoading ? 'Generating…' : insight ? 'Insights generated' : 'Generate AI Insights'}
              </button>
              {insightLoading && <div className="status loading"><span className="spinner" /> Requesting one concise explanation…</div>}
              {insightError && <div className="status error" role="alert">{insightError}</div>}
              {insight && <pre className="insight-result">{insight}</pre>}
            </section>
          </div>
        )}
      </main>

      <footer>
        SalesSight Lite • Educational demo • Forecasts are estimates, not business guarantees.
      </footer>
    </div>
  )
}

export default App

