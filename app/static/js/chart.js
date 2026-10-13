// Column chart of registrations per day: one series, thin bars, hover tooltip.
import { h, svg } from "./ui.js";

const HEIGHT = 210;
const MARGIN = { left: 30, right: 8, top: 22, bottom: 26 };

/** series: [{ date: "YYYY-MM-DD", count }] oldest first. Returns the element to insert. */
export function registrationsChart(series) {
  const drawing = svg("svg", { role: "img" });
  const tooltip = h("div", { class: "tooltip" });
  const root = h("div", { class: "chart" }, drawing, tooltip);
  const label = (iso) => new Date(iso + "T00:00:00").toLocaleDateString([], { month: "short", day: "numeric" });
  const total = series.reduce((sum, day) => sum + day.count, 0);
  drawing.setAttribute("aria-label",
    `Registrations per day, ${series.length} days, ${total} in total. ` +
    (series.filter((day) => day.count).map((day) => `${label(day.date)}: ${day.count}`).join(", ") || "None in this period") + ".");

  const draw = () => {
    const width = Math.max(280, root.clientWidth || 640);
    const peak = Math.max(...series.map((day) => day.count));
    const step = Math.max(1, Math.ceil(peak / 4));
    const top = Math.max(step, Math.ceil(peak / step) * step);
    const innerWidth = width - MARGIN.left - MARGIN.right;
    const innerHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
    const band = innerWidth / series.length;
    const barWidth = Math.max(3, Math.min(24, band - 4));
    const y = (value) => MARGIN.top + innerHeight - (value / top) * innerHeight;
    // Show as many date labels as fit without touching.
    const every = Math.max(1, Math.ceil(52 / band));

    drawing.setAttribute("viewBox", `0 0 ${width} ${HEIGHT}`);
    drawing.replaceChildren();
    for (let tick = 0; tick <= top; tick += step) {
      drawing.append(svg("line", {
        x1: MARGIN.left, x2: width - MARGIN.right, y1: y(tick), y2: y(tick),
        stroke: tick === 0 ? "var(--axis)" : "var(--grid)", "stroke-width": 1,
      }));
      const text = svg("text", { x: MARGIN.left - 8, y: y(tick) + 4, "text-anchor": "end" });
      text.textContent = tick;
      drawing.append(text);
    }
    series.forEach((day, index) => {
      const centre = MARGIN.left + band * index + band / 2;
      const fromEnd = series.length - 1 - index;
      if (fromEnd % every === 0) {
        const text = svg("text", { x: centre, y: HEIGHT - 8, "text-anchor": fromEnd === 0 ? "end" : "middle" });
        text.textContent = fromEnd === 0 ? "Today" : label(day.date);
        if (fromEnd === 0) text.setAttribute("x", centre + band / 2 - 2);
        drawing.append(text);
      }
      const hit = svg("rect", { class: "band", x: centre - band / 2, y: MARGIN.top, width: band, height: innerHeight, fill: "transparent" });
      const barTop = y(day.count);
      const radius = Math.min(4, barWidth / 2, (y(0) - barTop) / 2);
      const left = centre - barWidth / 2;
      const bar = svg("path", {
        class: "bar",
        d: day.count
          ? `M${left},${y(0)}V${barTop + radius}Q${left},${barTop} ${left + radius},${barTop}` +
            `H${left + barWidth - radius}Q${left + barWidth},${barTop} ${left + barWidth},${barTop + radius}V${y(0)}Z`
          : "",
      });
      drawing.append(hit, bar);
      if (day.count && day.count === peak) {
        const value = svg("text", { class: "value-label", x: centre, y: barTop - 6, "text-anchor": "middle" });
        value.textContent = day.count;
        drawing.append(value);
      }
      hit.addEventListener("mouseenter", () => {
        tooltip.replaceChildren(`${day.count} ${day.count === 1 ? "registration" : "registrations"} `,
                                h("span", null, `· ${label(day.date)}`));
        tooltip.style.left = `${Math.min(Math.max(centre, 70), width - 70)}px`;
        tooltip.style.top = `${barTop - 8}px`;
        tooltip.classList.add("show");
      });
      hit.addEventListener("mouseleave", () => tooltip.classList.remove("show"));
    });
  };

  new ResizeObserver(draw).observe(root);
  return root;
}
