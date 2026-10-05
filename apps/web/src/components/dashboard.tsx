import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  LoaderCircle,
  RefreshCw,
  UserRound,
  X,
} from "lucide-react";
import {
  Line,
  LineChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { createUsage, getUsage, getUser } from "../lib/api";
import {
  localInputValue,
  parseCustomRange,
  presets,
  randomUsage,
  summarize,
  type TimeFilter,
  type UsageRecord,
} from "../lib/usage";

const number = (value: number | null) =>
  value === null
    ? "—"
    : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
const dateTime = (value: string | number) =>
  new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });

function UsageChart({
  records,
  filter,
  updatedAt,
}: {
  records: UsageRecord[];
  filter: TimeFilter;
  updatedAt: number;
}) {
  const points = [...records]
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
    .map((record) => ({ ...record, time: Date.parse(record.timestamp) }));
  const end = filter.kind === "custom" ? Date.parse(filter.end) : updatedAt;
  const start =
    filter.kind === "custom"
      ? Date.parse(filter.start)
      : end - presets.find((preset) => preset.value === filter.value)!.duration;
  const domain = start === end ? [start - 30_000, end + 30_000] : [start, end];
  const longRange = end - start >= 24 * 60 * 60_000;
  return (
    <div
      className="chart-canvas"
      data-testid="usage-chart"
      aria-label={`Usage chart showing ${records.length} records. Hover over a point to inspect its value and timestamp.`}
    >
      <ResponsiveContainer width="100%" height={290}>
        <LineChart
          data={points}
          margin={{ top: 15, right: 16, left: -19, bottom: 8 }}
          accessibilityLayer
        >
          <CartesianGrid stroke="#e8e8e8" vertical={false} />
          <XAxis
            dataKey="time"
            type="number"
            domain={domain}
            tickCount={6}
            minTickGap={30}
            axisLine={false}
            tickLine={false}
            tickMargin={15}
            tick={{ fill: "#707070", fontSize: 12 }}
            tickFormatter={(time) =>
              new Date(time).toLocaleString(
                undefined,
                longRange
                  ? { month: "short", day: "numeric" }
                  : { hour: "2-digit", minute: "2-digit" },
              )
            }
          />
          <YAxis
            domain={[
              0,
              (max: number) => Math.max(100, Math.ceil(max / 25) * 25),
            ]}
            tickCount={5}
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#707070", fontSize: 12 }}
            tickMargin={10}
          />
          <Tooltip
            content={({ active, payload }) => {
              const point = payload?.[0]?.payload as
                (UsageRecord & { time: number }) | undefined;
              return active && point ? (
                <div className="chart-tooltip">
                  <span>{dateTime(point.time)}</span>
                  <strong>
                    {number(point.usage)} <small>units</small>
                  </strong>
                  <span>Record #{point.usage_id}</span>
                </div>
              ) : null;
            }}
          />
          <Line
            type="linear"
            dataKey="usage"
            name="Usage"
            stroke="#262626"
            strokeWidth={2}
            dot={{ r: 3, fill: "#262626", stroke: "#fff", strokeWidth: 1.5 }}
            activeDot={{ r: 5, stroke: "#fff", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Dashboard() {
  const client = useQueryClient();
  const [filter, setFilter] = useState<TimeFilter>({
    kind: "preset",
    value: "7d",
  });
  const [showCustomRange, setShowCustomRange] = useState(false);
  const [customRange, setCustomRange] = useState({ start: "", end: "" });
  const [rangeError, setRangeError] = useState("");
  const [notice, setNotice] = useState("");
  const [timezone, setTimezone] = useState("your local timezone");
  useEffect(() => {
    setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone);
  }, []);

  const user = useQuery({
    queryKey: ["user"],
    queryFn: ({ signal }) => getUser(signal),
  });
  const history = useQuery({
    queryKey: ["usage", filter],
    queryFn: ({ signal }) => getUsage(filter, signal),
  });
  const stats = summarize(history.data ?? []);
  const mutation = useMutation({
    mutationFn: () => createUsage(randomUsage()),
    onMutate: () => setNotice(""),
    onSuccess: async (record) => {
      const outside =
        filter.kind === "custom" &&
        (Date.parse(record.timestamp) < Date.parse(filter.start) ||
          Date.parse(record.timestamp) > Date.parse(filter.end));
      setNotice(
        `Saved ${number(record.usage)} units. Refreshing your dashboard…`,
      );
      await Promise.all([
        client.invalidateQueries({ queryKey: ["user"] }),
        client.invalidateQueries({ queryKey: ["usage"] }),
      ]);
      if (
        client.getQueryState(["user"])?.status === "error" ||
        client.getQueryState(["usage", filter])?.status === "error"
      ) {
        setNotice(
          `Saved ${number(record.usage)} units. The refresh failed; use Refresh to fetch your latest data.`,
        );
      } else {
        setNotice(
          `Saved ${number(record.usage)} units.${outside ? " This new record is outside your selected range." : " Your dashboard is up to date."}`,
        );
      }
    },
  });
  const refreshing = user.isFetching || history.isFetching;
  const error =
    mutation.error?.message || user.error?.message || history.error?.message;
  const filterLabel =
    filter.kind === "preset"
      ? `Last ${presets.find((preset) => preset.value === filter.value)!.label}`
      : "Custom range";
  function refresh() {
    mutation.reset();
    void Promise.all([user.refetch(), history.refetch()]);
  }
  function openCustomRange() {
    if (!customRange.start && !customRange.end) {
      const end = new Date();
      const duration =
        filter.kind === "preset"
          ? presets.find((preset) => preset.value === filter.value)!.duration
          : 7 * 24 * 60 * 60_000;
      setCustomRange({
        start: localInputValue(new Date(end.getTime() - duration)),
        end: localInputValue(end),
      });
    }
    setRangeError("");
    setShowCustomRange(true);
  }
  function applyCustomRange() {
    try {
      setFilter(parseCustomRange(customRange.start, customRange.end));
      setRangeError("");
    } catch (error) {
      setRangeError(
        error instanceof Error ? error.message : "Choose a valid date range.",
      );
    }
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to dashboard
      </a>
      <div className="workspace">
        <header className="topbar">
          <a href="/" className="wordmark">
            Cypienta
          </a>
          <div className="topbar-right">
            <section className="navbar-user" aria-label="User information">
              <span className="user-avatar" aria-hidden="true">
                <UserRound size={20} />
              </span>
              <div className="user-identity">
                <h2>
                  {user.data?.name ||
                    (user.isPending
                      ? "Loading user…"
                      : "User details unavailable")}
                </h2>
                <div className="user-metadata">
                  <span>
                    User ID{" "}
                    {user.data
                      ? `#${String(user.data.user_id).padStart(3, "0")}`
                      : "—"}
                  </span>
                  <span>
                    Member since{" "}
                    {user.data
                      ? new Date(user.data.created_at).toLocaleDateString(
                          undefined,
                          {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          },
                        )
                      : "—"}
                  </span>
                </div>
              </div>
            </section>
          </div>
        </header>
        <main id="main" className="main-content">
          <div className="page-heading">
            <div>
              <h1>Usage overview</h1>
            </div>
            <button
              className="button button-primary"
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
            >
              {mutation.isPending && (
                <LoaderCircle size={16} className="spin" />
              )}
              {mutation.isPending ? "Simulating…" : "Simulate Usage"}
            </button>
          </div>

          {error && (
            <div className="notice error-notice" role="alert">
              <Activity size={18} />
              <div>
                <strong>
                  {mutation.error
                    ? "Simulation could not be confirmed"
                    : "Unable to load the latest data"}
                </strong>
                <p>
                  {error}
                  {mutation.error
                    ? " Refresh activity before trying again."
                    : history.data
                      ? " Previously loaded records are still shown."
                      : ""}
                </p>
              </div>
              <button
                className="text-button"
                onClick={refresh}
                disabled={refreshing}
              >
                Retry
              </button>
            </div>
          )}
          {notice && (
            <div className="notice success-notice" role="status">
              <span className="success-icon">✓</span>
              <p>{notice}</p>
              <button
                className="icon-button"
                onClick={() => setNotice("")}
                aria-label="Dismiss notification"
              >
                <X size={16} />
              </button>
            </div>
          )}

          <section
            className="card chart-card"
            id="usage"
            aria-label="Usage over time"
          >
            <div className="section-heading">
              <button
                className="button button-secondary refresh-button"
                onClick={refresh}
                disabled={refreshing || mutation.isPending}
              >
                <RefreshCw size={14} className={refreshing ? "spin" : ""} />{" "}
                Refresh
              </button>
            </div>
            <div className="filter-bar">
              <div
                className="presets"
                role="group"
                aria-label="Time-frame presets"
              >
                {presets.map((preset) => (
                  <button
                    key={preset.value}
                    disabled={mutation.isPending}
                    aria-pressed={
                      filter.kind === "preset" && filter.value === preset.value
                    }
                    className={`preset ${filter.kind === "preset" && filter.value === preset.value ? "selected" : ""}`}
                    onClick={() => {
                      setFilter({ kind: "preset", value: preset.value });
                      setShowCustomRange(false);
                      setRangeError("");
                    }}
                  >
                    {preset.label}
                  </button>
                ))}
                <button
                  type="button"
                  className={`preset ${filter.kind === "custom" ? "selected" : ""}`}
                  aria-pressed={filter.kind === "custom"}
                  aria-expanded={showCustomRange}
                  aria-controls="custom-range"
                  disabled={mutation.isPending}
                  onClick={openCustomRange}
                >
                  Custom range
                </button>
              </div>
              {showCustomRange && (
                <form
                  id="custom-range"
                  className="custom-range"
                  aria-label="Custom datetime range"
                  noValidate
                  onSubmit={(event) => {
                    event.preventDefault();
                    applyCustomRange();
                  }}
                >
                  <label className="range-field">
                    Start date and time
                    <input
                      type="datetime-local"
                      value={customRange.start}
                      required
                      disabled={mutation.isPending}
                      aria-invalid={Boolean(rangeError)}
                      aria-describedby={`range-timezone${rangeError ? " range-error" : ""}`}
                      onChange={(event) => {
                        setCustomRange((range) => ({
                          ...range,
                          start: event.target.value,
                        }));
                        setRangeError("");
                      }}
                    />
                  </label>
                  <label className="range-field">
                    End date and time
                    <input
                      type="datetime-local"
                      value={customRange.end}
                      required
                      disabled={mutation.isPending}
                      aria-invalid={Boolean(rangeError)}
                      aria-describedby={`range-timezone${rangeError ? " range-error" : ""}`}
                      onChange={(event) => {
                        setCustomRange((range) => ({
                          ...range,
                          end: event.target.value,
                        }));
                        setRangeError("");
                      }}
                    />
                  </label>
                  <button
                    type="submit"
                    className="button button-secondary"
                    disabled={mutation.isPending}
                  >
                    Apply range
                  </button>
                  <p id="range-timezone" className="range-hint">
                    Times in {timezone}
                  </p>
                  {rangeError && (
                    <p id="range-error" className="range-error" role="alert">
                      {rangeError}
                    </p>
                  )}
                </form>
              )}
            </div>
            <div className="chart-meta">
              <span>
                <i /> Usage <span className="muted">/ units</span>
              </span>
              <span>
                {history.isFetching
                  ? "Updating records…"
                  : !history.data
                    ? "Records unavailable"
                    : `${stats.count} ${stats.count === 1 ? "record" : "records"}`}
                <span className="meta-dot">·</span>
                {filterLabel}
              </span>
            </div>
            {history.isPending ? (
              <div className="chart-placeholder" role="status">
                <LoaderCircle className="spin" size={24} />
                <p>Gathering your activity…</p>
              </div>
            ) : history.isError && !history.data ? (
              <div className="chart-placeholder">
                <Activity size={28} />
                <h3>Your chart is unavailable</h3>
                <p>Retry once your backend is connected.</p>
              </div>
            ) : stats.count === 0 ? (
              <div className="chart-placeholder">
                <span className="empty-icon">
                  <BarChart3 size={28} />
                </span>
                <h3>A fresh start</h3>
                <p>
                  No records in this time range. Try a wider range or simulate
                  some usage.
                </p>
              </div>
            ) : (
              <UsageChart
                records={stats.ordered}
                filter={filter}
                updatedAt={history.dataUpdatedAt}
              />
            )}
            <div className="chart-footer">
              <span>
                <span className="tiny-dot" />{" "}
                {filter.kind === "custom"
                  ? `${dateTime(filter.start)} — ${dateTime(filter.end)}`
                  : "Your activity in the selected time window"}
              </span>
              <span>{timezone}</span>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
