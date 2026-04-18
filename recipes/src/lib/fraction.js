function gcd(a, b) {
  a = Math.abs(a);
  b = Math.abs(b);
  while (b !== 0) {
    [a, b] = [b, a % b];
  }
  return a || 1;
}

export class Fraction {
  constructor(num, den) {
    if (den === 0) throw new Error("Fraction denominator cannot be 0");
    if (den < 0) {
      num = -num;
      den = -den;
    }
    const g = gcd(num, den);
    this.num = num / g;
    this.den = den / g;
  }

  static parse(str) {
    const s = String(str).trim();
    let m;
    if ((m = s.match(/^(\d+)\s+(\d+)\/(\d+)$/))) {
      const whole = +m[1],
        num = +m[2],
        den = +m[3];
      return new Fraction(whole * den + num, den);
    }
    if ((m = s.match(/^(\d+)\/(\d+)$/))) {
      return new Fraction(+m[1], +m[2]);
    }
    if ((m = s.match(/^(\d+)$/))) {
      return new Fraction(+m[1], 1);
    }
    throw new Error(`Cannot parse fraction: "${str}"`);
  }

  times(f) {
    return new Fraction(this.num * f.num, this.den * f.den);
  }
  div(f) {
    return new Fraction(this.num * f.den, this.den * f.num);
  }

  toString() {
    if (this.num === 0) return "0";
    if (this.den === 1) return String(this.num);
    const whole = Math.trunc(this.num / this.den);
    const rem = this.num - whole * this.den;
    if (whole === 0) return `${rem}/${this.den}`;
    if (rem === 0) return `${whole}`;
    return `${whole} ${rem}/${this.den}`;
  }
}
