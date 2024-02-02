const MIN_YEAR = 1582;
const CURRENT_YEAR = new Date().getFullYear();
const WEEK_DAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];
function isLeapYear(year) {
  return new Date(year, 1, 29).getDate() === 29;
}
function calc() {
  const output = document.getElementById("output");
  output.innerHTML = "";

  const year = Number(document.getElementById("year").value);
  if (Number.isNaN(year) || year < MIN_YEAR) return;

  const START_WEEK_DAY = new Date(year, 0, 1).getDay();
  const LEAP_YEAR = isLeapYear(year);

  const years = [];
  for (let y = MIN_YEAR; ; y++) {
    const startWeekDay = new Date(y, 0, 1).getDay();
    const leapYear = isLeapYear(y);
    if (startWeekDay === START_WEEK_DAY && leapYear === LEAP_YEAR) {
      years.push(y);
      if (y > year) {
        break;
      }
    }
  }

  output.appendChild(document.createElement("p")).innerHTML =
    "Start Week Day: " +
    WEEK_DAYS[START_WEEK_DAY] +
    "<br />Leap Year: " +
    (LEAP_YEAR ? "✅ Yes" : "❌ No");

  const yearList = output.appendChild(document.createElement("ul"));
  for (const y of years) {
    const link = yearList
      .appendChild(document.createElement("li"))
      .appendChild(document.createElement("a"));
    link.href = `https://www.ebay.com/sch/i.html?_nkw=${y}+calendar`;
    link.innerText = y;
    link.target = "_blank";
  }
}
