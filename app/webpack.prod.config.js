const path = require("path");

module.exports = {
  extends: path.resolve(__dirname, "webpack.base.config.js"),
  mode: "production",
  output: {
    filename: "prod-bundle.js",
    path: path.resolve(__dirname, "..", "docs", "assets"),
  },
};
