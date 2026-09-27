// Squarified treemap (Bruls, Huizing, van Wijk 2000).

export interface TreemapItem<T = unknown> {
  id: string;
  value: number;
  data?: T;
}

export interface TreemapRect<T = unknown> extends TreemapItem<T> {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

function worstRatio(row: number[], side: number): number {
  const sum = row.reduce((a, b) => a + b, 0);
  if (sum <= 0 || side <= 0) return Infinity;
  const max = Math.max(...row);
  const min = Math.min(...row);
  const s2 = side * side;
  const sum2 = sum * sum;
  return Math.max((s2 * max) / sum2, sum2 / (s2 * min));
}

/** Lay `items` out in a `width` x `height` box. Areas are proportional to `value`. */
export function squarify<T>(items: TreemapItem<T>[], width: number, height: number): TreemapRect<T>[] {
  const positive = items.filter((i) => i.value > 0).sort((a, b) => b.value - a.value);
  const total = positive.reduce((a, i) => a + i.value, 0);
  if (!positive.length || total <= 0 || width <= 0 || height <= 0) return [];

  const scale = (width * height) / total;
  const areas = positive.map((i) => i.value * scale);
  const out: TreemapRect<T>[] = [];
  const box: Box = { x: 0, y: 0, w: width, h: height };

  let i = 0;
  while (i < areas.length) {
    const side = Math.min(box.w, box.h);
    const row = [areas[i]];
    let j = i + 1;
    while (j < areas.length && worstRatio([...row, areas[j]], side) <= worstRatio(row, side)) {
      row.push(areas[j]);
      j++;
    }
    layoutRow(row, positive.slice(i, j), box, out);
    i = j;
  }
  return out;
}

function layoutRow<T>(row: number[], items: TreemapItem<T>[], box: Box, out: TreemapRect<T>[]) {
  const sum = row.reduce((a, b) => a + b, 0);
  if (box.w >= box.h) {
    // Vertical strip along the left edge.
    const stripW = sum / box.h;
    let y = box.y;
    row.forEach((area, k) => {
      const h = area / stripW;
      out.push({ ...items[k], x: box.x, y, w: stripW, h });
      y += h;
    });
    box.x += stripW;
    box.w -= stripW;
  } else {
    // Horizontal strip along the top edge.
    const stripH = sum / box.w;
    let x = box.x;
    row.forEach((area, k) => {
      const w = area / stripH;
      out.push({ ...items[k], x, y: box.y, w, h: stripH });
      x += w;
    });
    box.y += stripH;
    box.h -= stripH;
  }
}
