const LETTERS = "23456789ABCDEFGHJKMNPQRSTVWXYZ";

const badwords = require("badwords-list");
const blobStream = require("blob-stream");
const FileSaver = require("file-saver");
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

window.addEventListener("load", () => {
  document.getElementById("btnGenerate").addEventListener("click", async () => {
    const includeMoney = document.getElementById("chkMoney").checked;

    const doc = new PDFDocument({
      size: [153, 72],
      autoFirstPage: false,
      margin: 0,
    });
    const stream = doc.pipe(blobStream());
    stream.on("finish", () => {
      FileSaver(stream.toBlob("application/pdf"), "mft-gift-cards.pdf");
    });

    const count = document.getElementById("numCount").value;
    for (let i = 0; i < count; i++) {
      const rawCode = getCode();
      const formattedCode = rawCode.replace(/(...)(?!$)/g, "$1 ");

      const qrCode = QRCode.create(`shopify-giftcard-v1-${rawCode}`, {
        errorCorrectionLevel: "H",
      });
      const canvas = await QRCode.toCanvas(qrCode.segments);

      doc.addPage();

      const imageBlob = await new Promise((resolve) => canvas.toBlob(resolve));
      doc.image(await imageBlob.arrayBuffer(), includeMoney ? 12 : 49, 0, {
        width: 55,
        height: 55,
      });

      if (includeMoney) {
        doc.font("Helvetica", 24);
        doc.text("$____", 67, 20, { width: 98 });
      }

      const textOptions = { width: 153, align: "center" };

      let fontSize = 14;
      doc.font("Helvetica", fontSize);
      const width12 = doc.widthOfString(formattedCode, textOptions);

      if (width12 > 140) {
        doc.font("Helvetica", (fontSize * 140) / width12);
      }

      doc.text(formattedCode, 0, 55, textOptions);
    }

    doc.end();
  });
});
