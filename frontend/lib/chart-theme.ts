/** One palette for every chart. Gold = primary series, green = comparison
 * (the two-team pair of the match-centre look), light blue = reference, amber = caution. */
export const CHART = {
  cyan: "#E9B23C",
  violet: "#33C17A",
  emerald: "#7CC4F0",
  amber: "#F2B53A",
  red: "#E5394F",
  grid: "#22252D",
  axis: "#6B7180",
  text: "#A0A5B1",
  series: ["#E9B23C", "#33C17A", "#7CC4F0", "#E5394F", "#B48CF2", "#A0A5B1"],
};
export const axisProps = {
  stroke: CHART.axis,
  tick: { fill: CHART.text, fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: CHART.grid },
};

export const tooltipStyle = {
  contentStyle: {
    background: "#1C1F27",
    border: "1px solid #2E323C",
    borderRadius: 4,
    fontSize: 12,
    color: "#ECEEF2",
  },
  labelStyle: { color: "#A0A5B1", marginBottom: 4 },
  itemStyle: { color: "#ECEEF2" },
  cursor: { stroke: "#2E323C", fill: "rgba(229,57,79,0.06)" },
};
