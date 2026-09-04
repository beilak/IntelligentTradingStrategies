import type {
  BacktestResult,
  CpcvResult,
  Locale,
  WalkForwardResult,
} from "./types";

export type TestReport = CpcvResult | WalkForwardResult | BacktestResult;

type Labels = {
  assets: string;
  description: string;
  field: string;
  generatedAt: string;
  metadata: string;
  metric: string;
  model: string;
  parameters: string;
  periods: string;
  rawData: string;
  rawDataNote: string;
  results: string;
  strategy: string;
  test: string;
  testType: string;
  value: string;
};

const LABELS: Record<Locale, Labels> = {
  ru: {
    assets: "Активы",
    description: "Описание стратегии",
    field: "Поле",
    generatedAt: "Сформирован",
    metadata: "Общая информация",
    metric: "Метрика",
    model: "Модель",
    parameters: "Параметры запуска",
    periods: "Периоды данных",
    rawData: "Полный набор данных",
    rawDataNote: "Схема и значения API сохранены без сокращений в JSON-блоке в конце отчёта.",
    results: "Результаты",
    strategy: "Стратегия",
    test: "Тест",
    testType: "Тип теста",
    value: "Значение",
  },
  en: {
    assets: "Assets",
    description: "Strategy description",
    field: "Field",
    generatedAt: "Generated at",
    metadata: "General information",
    metric: "Metric",
    model: "Model",
    parameters: "Run parameters",
    periods: "Data periods",
    rawData: "Complete data set",
    rawDataNote: "The API schema and values are preserved without truncation in the JSON block at the end of this report.",
    results: "Results",
    strategy: "Strategy",
    test: "Test",
    testType: "Test type",
    value: "Value",
  },
};

function markdownValue(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value).replace(/\|/g, "\\|").replace(/\r?\n/g, "<br>");
}

function table(headers: string[], rows: unknown[][]): string {
  if (!rows.length) return "_—_";
  return [
    `| ${headers.join(" | ")} |`,
    `| ${headers.map(() => "---").join(" | ")} |`,
    ...rows.map((row) => `| ${row.map(markdownValue).join(" | ")} |`),
  ].join("\n");
}

function periodRows(result: TestReport): unknown[][] {
  const metadata = result.metadata;
  if ("price_period" in metadata) {
    return [
      ["price", metadata.price_period.start, metadata.price_period.end, metadata.price_period.rows],
      ["trading", metadata.trading_period.start, metadata.trading_period.end, metadata.trading_period.rows],
    ];
  }
  return [
    ["train", metadata.train_period.start, metadata.train_period.end, metadata.train_period.rows],
    ["test", metadata.test_period.start, metadata.test_period.end, metadata.test_period.rows],
  ];
}

function metricSections(result: TestReport, labels: Labels): string[] {
  const sections: string[] = [];
  if ("summary" in result) {
    sections.push(
      "### Summary",
      table(
        [labels.metric, labels.value, "numeric_value"],
        result.summary.map((row) => [row.metric, row.value, row.numeric_value]),
      ),
    );
  }
  if ("cv_summary" in result) {
    sections.push(
      "### CV summary",
      table(
        [labels.metric, labels.value, "numeric_value"],
        result.cv_summary.map((row) => [row.metric, row.value, row.numeric_value]),
      ),
    );
  }
  sections.push(
    "### Report",
    table(
      [labels.metric, labels.value, "numeric_value"],
      result.report.map((row) => [row.metric, row.value, row.numeric_value]),
    ),
  );
  return sections;
}

function pathDetails(
  result: {
    paths: Array<{
      name: string;
      final_return: number;
      points: Array<{ time: string; value: number }>;
    }>;
  },
  heading: string,
): string[] {
  return [
    `### ${heading}`,
    table(
      ["name", "final_return", "points", "start", "end"],
      result.paths.map((path) => [
        path.name,
        path.final_return,
        path.points.length,
        path.points[0]?.time,
        path.points[path.points.length - 1]?.time,
      ]),
    ),
  ];
}

function walkForwardDetails(result: WalkForwardResult): string[] {
  const sections = [
    "### WalkForward windows",
    table(
      ["split_id", "train_start", "train_end", "train_rows", "test_start", "test_end", "test_rows"],
      (result.windows ?? []).map((window) => [
        window.split_id,
        window.train_start,
        window.train_end,
        window.train_rows,
        window.test_start,
        window.test_end,
        window.test_rows,
      ]),
    ),
  ];
  if (result.oos_curve) {
    sections.push(
      "### Stitched OOS curve",
      table(
        ["name", "stitch_rule", "final_return", "rows", "duplicates_removed", "points"],
        [[
          result.oos_curve.name,
          result.oos_curve.stitch_rule,
          result.oos_curve.final_return,
          result.oos_curve.rows,
          result.oos_curve.duplicates_removed,
          result.oos_curve.points.length,
        ]],
      ),
    );
  }
  sections.push(...pathDetails(result, "WalkForward paths"));
  return sections;
}

function backtestDetails(result: BacktestResult): string[] {
  const curveRows = [result.equity_curve, result.drawdown_curve, result.rolling_sharpe].map(
    (curve) => [
      curve.name,
      curve.final_value,
      curve.points.length,
      curve.points[0]?.time,
      curve.points[curve.points.length - 1]?.time,
    ],
  );
  const weightRows = result.rebalance_weights.flatMap((record) =>
    record.weights.length
      ? record.weights.map((weight) => [
          record.time,
          record.total_weight,
          record.asset_count,
          weight.ticker,
          weight.weight,
          weight.sector,
        ])
      : [[record.time, record.total_weight, record.asset_count, "CASH", 0, null]],
  );
  return [
    "### Curves",
    table(["name", "final_value", "points", "start", "end"], curveRows),
    "### Rebalance weights",
    table(
      ["time", "total_weight", "asset_count", "ticker", "weight", "sector"],
      weightRows,
    ),
    "### Execution events",
    table(
      [
        "time",
        "ticker",
        "reason",
        "entry_time",
        "entry_price",
        "execution_price",
        "threshold_price",
        "return_pct",
        "weight",
      ],
      result.execution_events.map((event) => [
        event.time,
        event.ticker,
        event.reason,
        event.entry_time,
        event.entry_price,
        event.execution_price,
        event.threshold_price,
        event.return_pct,
        event.weight,
      ]),
    ),
  ];
}

export function buildMarkdownReport(result: TestReport, locale: Locale): string {
  const labels = LABELS[locale];
  const { metadata } = result;
  const normalizedTestType = metadata.test_type.toLowerCase().replace(/[^a-z]/g, "");
  const details =
    normalizedTestType === "cpcv"
      ? pathDetails(result as CpcvResult, "CPCV paths")
      : normalizedTestType === "walkforward"
        ? walkForwardDetails(result as WalkForwardResult)
        : backtestDetails(result as BacktestResult);

  return [
    `# ${metadata.test_name} — ${metadata.test_type}`,
    `> ${labels.rawDataNote}`,
    `## ${labels.metadata}`,
    table(
      [labels.field, labels.value],
      [
        [labels.test, metadata.test_name],
        [labels.testType, metadata.test_type],
        [labels.model, metadata.model_name],
        [labels.strategy, metadata.strategy_name],
        [labels.description, metadata.strategy_description],
        [labels.generatedAt, metadata.generated_at],
        ["source", "source" in metadata ? metadata.source : undefined],
        ["entity_type", "entity_type" in metadata ? metadata.entity_type : undefined],
      ],
    ),
    `## ${labels.parameters}`,
    table(
      [labels.field, labels.value],
      Object.entries(metadata.settings).map(([key, value]) => [key, value]),
    ),
    `## ${labels.periods}`,
    table(["period", "start", "end", "rows"], periodRows(result)),
    `## ${labels.assets} (${metadata.asset_count})`,
    table(
      ["figi", "ticker", "name", "sector"],
      metadata.assets.map((asset) => [asset.figi, asset.ticker, asset.name, asset.sector]),
    ),
    `## ${labels.results}`,
    ...metricSections(result, labels),
    ...details,
    `## ${labels.rawData}`,
    "```json",
    JSON.stringify(result, null, 2),
    "```",
    "",
  ].join("\n\n");
}

export function reportFileName(result: TestReport): string {
  const safeTestName = result.metadata.test_name
    .trim()
    .replace(/[^a-zA-Z0-9А-яЁё._-]+/g, "-")
    .replace(/^-+|-+$/g, "") || "report";
  return `${safeTestName}-${result.metadata.test_type}.md`;
}

export function downloadMarkdownReport(result: TestReport, locale: Locale): void {
  const blob = new Blob([buildMarkdownReport(result, locale)], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = reportFileName(result);
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
