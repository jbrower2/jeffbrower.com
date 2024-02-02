const COUNT = 1;
const LETTERS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

const fs = require("fs");

const badwords = require("badwords-list");
const PDFDocument = require("pdfkit");
const QRCode = require("qrcode");

function getCode() {
  while (true) {
    const code =
      "MFT" +
      Array(12)
        .fill(null)
        .map(() => LETTERS[Math.floor(Math.random() * LETTERS.length)])
        .join("");

    const lower = code.toLowerCase();
    const foundBadwords = badwords.array.filter((badword) =>
      lower.includes(badword)
    );
    if (foundBadwords.length === 0) {
      return code;
    }

    console.log("Found bad word(s) in", code, foundBadwords);
  }
}

async function main() {
  const doc = new PDFDocument({
    size: [153, 72],
    autoFirstPage: false,
    margin: 0,
  });
  doc.pipe(fs.createWriteStream("mft-gift-cards.pdf"));

  for (let i = 0; i < COUNT; i++) {
    const rawCode = getCode();
    const formattedCode = rawCode.replace(/(...)(?!$)/g, "$1 ");

    const qrCode = QRCode.create(`shopify-giftcard-v1-${rawCode}`, {
      errorCorrectionLevel: "H",
    });
    const buf = await new Promise((resolve, reject) =>
      QRCode.toBuffer(qrCode.segments, (err, buf) =>
        err ? reject(err) : resolve(buf)
      )
    );

    doc.addPage();

    doc.image(buf, 47.5, 0, { width: 58, height: 58 });

    const textOptions = { width: 153, align: "center" };

    let fontSize = 12;
    doc.font("Helvetica", fontSize);
    const width12 = doc.widthOfString(formattedCode, textOptions);

    if (width12 > 150) {
      doc.font("Helvetica", (fontSize * 150) / width12);
    }

    doc.text(formattedCode, 0, 58, textOptions);
  }

  doc.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
