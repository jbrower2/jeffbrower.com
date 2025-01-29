const path = require("path");

module.exports = {
  extends: path.resolve(__dirname, "webpack.base.config.js"),
  mode: "development",
  devServer: {
    static: "./dist",
  },
  output: {
    filename: "dev-bundle.js",
    path: path.resolve(__dirname, "dist"),
  },
};
