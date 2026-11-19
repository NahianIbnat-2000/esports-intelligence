/** One palette for every chart, terminal style. Amber = primary series, blue = comparison,
 * green = reference, red = negative, yellow = caution. */
export const CHART = {
  cyan: "#FF9F1C",
  violet: "#4DA3FF",
  emerald: "#2BD67B",
  amber: "#F5D547",
  red: "#FF4D4F",
  grid: "#1C2026",
  axis: "#626973",
  text: "#9AA0A9",
  series: ["#FF9F1C", "#4DA3FF", "#2BD67B", "#FF4D4F", "#B48CF2", "#9AA0A9"],
};
export const axisProps = {
  stroke: CHART.axis,
  tick: { fill: CHART.text, fontSize: 10.5, fontFamily: "IBM Plex Mono, monospace" },
  tickLine: false,
  axisLine: { stroke: CHART.grid },
};

export const tooltipStyle = {
  contentStyle: {
    background: "#15181D",
    border: "1px solid #2C3138",
    borderRadius: 2,
    fontSize: 12,
    fontFamily: "IBM Plex Mono, monospace",
    color: "#E6E8EB",
  },
  labelStyle: { color: "#9AA0A9", marginBottom: 4 },
  itemStyle: { color: "#E6E8EB" },
  cursor: { stroke: "#2C3138", fill: "rgba(255,159,28,0.06)" },
};
