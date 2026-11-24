export type CardImage = {
  kind: "patient" | "doctor";
  title: string;
  name: string;
  locale: string;
  identifier?: { label: string; value: string };
  fields: { label: string; value: string }[];
  footer?: string;
};

function drawText(
  context: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  maxHeight: number,
  locale: string,
  size = 14,
  weight = 500,
  color = "#173c35",
) {
  const words = text.split(/(\s+)/u);
  const segmenter = new Intl.Segmenter(locale, { granularity: "grapheme" });
  let lines: string[] = [];
  let fontSize = size;
  for (; fontSize >= 3; fontSize -= 0.5) {
    context.font = `${weight} ${fontSize}px system-ui, sans-serif`;
    lines = [""];
    for (const word of words) {
      const index = lines.length - 1;
      if (context.measureText(lines[index] + word).width <= maxWidth) {
        if (lines[index] || word.trim()) lines[index] += word;
        continue;
      }
      if (!word.trim()) continue;
      if (lines[index]) lines.push("");
      for (const part of segmenter.segment(word)) {
        const last = lines.length - 1;
        if (lines[last] && context.measureText(lines[last] + part.segment).width > maxWidth)
          lines.push(part.segment);
        else lines[last] += part.segment;
      }
    }
    if (lines.length * fontSize * 1.2 <= maxHeight) break;
  }
  context.fillStyle = color;
  context.textBaseline = "top";
  lines.forEach((line, index) => {
    context.fillText(line, x, y + index * fontSize * 1.2);
  });
}

async function setPrintResolution(png: Blob): Promise<Blob> {
  // PNG pHYs stores pixels per metre; 1050 × 600 pixels at 300 DPI prints at 3.5 × 2 inches.
  const physical = new Uint8Array(21);
  const view = new DataView(physical.buffer);
  view.setUint32(0, 9);
  physical.set([112, 72, 89, 115], 4);
  view.setUint32(8, Math.round(300 / 0.0254));
  view.setUint32(12, Math.round(300 / 0.0254));
  physical[16] = 1;
  let crc = 0xffffffff;
  for (const byte of physical.subarray(4, 17)) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  view.setUint32(17, (crc ^ 0xffffffff) >>> 0);
  const bytes = await png.arrayBuffer();
  const source = new DataView(bytes);
  const parts: BlobPart[] = [bytes.slice(0, 8)];
  for (let offset = 8; offset + 12 <= bytes.byteLength; ) {
    const end = offset + source.getUint32(offset) + 12;
    if (end > bytes.byteLength) throw new Error("Invalid card image");
    const type = String.fromCharCode(...new Uint8Array(bytes, offset + 4, 4));
    if (type !== "pHYs") parts.push(bytes.slice(offset, end));
    if (type === "IHDR") parts.push(physical.buffer);
    offset = end;
  }
  return new Blob(parts, { type: "image/png" });
}

export async function createCardImage(card: CardImage): Promise<Blob> {
  await document.fonts.ready;
  const canvas = document.createElement("canvas");
  canvas.width = 1050;
  canvas.height = 600;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Card image unavailable");
  context.scale(canvas.width / 336, canvas.height / 192);
  const wash = context.createLinearGradient(0, 0, 336, 192);
  wash.addColorStop(0, "#ffffff");
  wash.addColorStop(1, "#edf8f2");
  context.fillStyle = wash;
  context.fillRect(0, 0, 336, 192);
  context.fillStyle = "#17695d";
  context.fillRect(0, 0, 5, 192);
  drawText(context, "CareGap 360", 16, 13, 104, 20, card.locale, 14, 700);
  drawText(context, card.title, 128, 15, 192, 17, card.locale, 11);
  context.strokeStyle = "#c7ded4";
  context.beginPath();
  context.moveTo(16, 37);
  context.lineTo(320, 37);
  context.stroke();
  drawText(context, card.name, 16, 48, card.identifier ? 210 : 304, 43, card.locale, 18, 700);
  if (card.identifier) {
    drawText(context, card.identifier.label, 242, 48, 78, 16, card.locale, 11);
    drawText(context, card.identifier.value, 242, 65, 78, 29, card.locale, 25, 700);
  }
  card.fields.forEach((field, index) => {
    const fullRow = card.kind === "doctor" && index === 0;
    const cell = card.kind === "doctor" ? index - 1 : index;
    const x = fullRow ? 16 : 16 + (cell % 2) * 158;
    const y = card.kind === "doctor" ? (fullRow ? 98 : 142) : 100 + Math.floor(cell / 2) * 42;
    const cellWidth = fullRow ? 304 : 146;
    drawText(context, field.label, x, y, cellWidth, 14, card.locale, 10, 500, "#52665e");
    drawText(context, field.value, x, y + 15, cellWidth, 24, card.locale, 13, 650);
  });
  if (card.footer) drawText(context, card.footer, 16, 120, 304, 52, card.locale, 12, 500, "#52665e");
  const png = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("Card image unavailable"))),
      "image/png",
    );
  });
  return setPrintResolution(png);
}

export function saveCardImage(image: Blob, filename: string) {
  const url = URL.createObjectURL(image);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
