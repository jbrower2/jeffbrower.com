const CATEGORIES = new Set([
  "Breakfast",
  "Dessert/Bread",
  "Dessert/Brownies",
  "Dessert/Cake",
  "Dessert/Cake/Cheesecake",
  "Dessert/Cake/Cheesecake/Shells",
  "Dessert/Cake/Whoopie Pies",
  "Dessert/Candy",
  "Dessert/Cannolis/Filling",
  "Dessert/Cannolis/Shells",
  "Dessert/Cookies",
  "Dessert/Cookies/Pizzelles",
  "Dessert/Cupcakes",
  "Dessert/Donuts",
  "Dessert/Frosting/Custard",
  "Dessert/Frosting/Frosting",
  "Dessert/Frosting/Icing",
  "Dessert/Fudge",
  "Dessert/Ice Cream",
  "Dessert/Muffins",
  "Dessert/Pastry",
  "Dessert/Pie",
  "Dessert/Pie/Pie Crusts",
  "Appetizer",
  "Drink",
  "Main Dish",
  "Seasoning",
  "Side Dish",
]);

const recipes = [];

function nameFromMarkdown(md) {
  const firstLine = md.split("\n", 1)[0];
  return firstLine.replace(/^#\s*/, "").trim();
}

function addRecipe(slug, categories, shown) {
  for (const c of categories) {
    if (!CATEGORIES.has(c)) {
      throw new Error(`Unknown category "${c}" for ${slug}`);
    }
  }
  const markdown = require(`./${slug}.md`);
  recipes.push({
    slug,
    name: nameFromMarkdown(markdown),
    show: shown === true,
    categories,
    markdown,
  });
}

addRecipe("almond-pastry-cream", ["Dessert/Frosting/Custard"]);
addRecipe("apple-bread", ["Dessert/Bread"]);
addRecipe("apple-cider", ["Drink"], true);
addRecipe("apple-cider-doughnuts", ["Dessert/Donuts"], true);
addRecipe("apple-fritters", ["Dessert/Donuts"]);
addRecipe("apple-muffins", ["Dessert/Muffins"]);
addRecipe("apple-pear-pie", ["Dessert/Pie"]);
addRecipe("b-and-ls-strawberry-smoothie", ["Drink"], true);
addRecipe("banana-bread-muffins", ["Dessert/Bread", "Dessert/Muffins"]);
addRecipe("banana-cream-pie", ["Dessert/Pie"]);
addRecipe("banana-orange-bread-muffins", ["Dessert/Bread", "Dessert/Muffins"]);
addRecipe("best-chocolate-cupcakes", ["Dessert/Cupcakes"], true);
addRecipe("biscotti", ["Dessert/Cookies"]);
addRecipe("black-and-white-cookies", ["Dessert/Cookies"]);
addRecipe("blackened-mahi-mahi", ["Main Dish"], true);
addRecipe("blonde-brownies", ["Dessert/Brownies"]);
addRecipe("blueberry-bread-muffins", ["Dessert/Bread", "Dessert/Muffins"]);
addRecipe("blueberry-pie", ["Dessert/Pie"]);
addRecipe("boston-cream", ["Dessert/Frosting/Custard"]);
addRecipe("brown-butter-frosting", ["Dessert/Frosting/Frosting"]);
addRecipe("brown-butter-frosting-icing", ["Dessert/Frosting/Frosting"]);
addRecipe("brown-sugar-glazed-salmon", ["Main Dish"], true);
addRecipe("butter-pecan-fudge", ["Dessert/Fudge"]);
addRecipe("butterbeer", ["Drink"]);
addRecipe("cake-batter-fudge", ["Dessert/Fudge"]);
addRecipe("candy-cane-fudge", ["Dessert/Fudge"]);
addRecipe("candy-corn", ["Dessert/Candy"]);
addRecipe("cannoli-filling", ["Dessert/Cannolis/Filling"]);
addRecipe("cannoli-shells", ["Dessert/Cannolis/Shells"]);
addRecipe("caramel-shortbread-cookies", ["Dessert/Cookies"]);
addRecipe("carrot-cake", ["Dessert/Cake"], true);
addRecipe("carrot-cake-cupcakes", ["Dessert/Cupcakes"], true);
addRecipe("cheesecake", ["Dessert/Cake/Cheesecake"]);
addRecipe("cheesecake-shell", ["Dessert/Cake/Cheesecake/Shells"]);
addRecipe("cheesy-hashbrown-casserole", ["Side Dish"], true);
addRecipe("cherry-banana-bread-muffins", ["Dessert/Bread", "Dessert/Muffins"]);
addRecipe("cherry-pie", ["Dessert/Pie"]);
addRecipe("chocolate-brownies", ["Dessert/Brownies"]);
addRecipe("chocolate-buttercream-frosting", ["Dessert/Frosting/Frosting"]);
addRecipe("chocolate-cake", ["Dessert/Cake"]);
addRecipe("chocolate-cannoli-shells", ["Dessert/Cannolis/Shells"]);
addRecipe("chocolate-cannolis", ["Dessert/Cannolis/Filling"]);
addRecipe("chocolate-cheesecake", ["Dessert/Cake/Cheesecake"]);
addRecipe("chocolate-chip-cinnamon-pizzelles", ["Dessert/Cookies/Pizzelles"]);
addRecipe("chocolate-chip-cookie-dough-fudge", ["Dessert/Fudge"]);
addRecipe("chocolate-chip-cookies", ["Dessert/Cookies"]);
addRecipe("chocolate-chip-cupcakes", ["Dessert/Cupcakes"]);
addRecipe("chocolate-chocolate-chip-cookies", ["Dessert/Cookies"], true);
addRecipe("chocolate-chocolate-chip-cookies-old", ["Dessert/Cookies"]);
addRecipe("chocolate-cinnamon-fudge", ["Dessert/Fudge"]);
addRecipe("chocolate-covered-pretzels", ["Dessert/Candy"]);
addRecipe("chocolate-crinkle-cookies", ["Dessert/Cookies"], true);
addRecipe("chocolate-cream-pie", ["Dessert/Pie"]);
addRecipe("chocolate-donuts", ["Dessert/Donuts"]);
addRecipe("chocolate-eclairs", ["Dessert/Pastry"]);
addRecipe("chocolate-fudge", ["Dessert/Fudge"]);
addRecipe("chocolate-icing", ["Dessert/Frosting/Icing"]);
addRecipe("chocolate-orange-fudge", ["Dessert/Fudge"]);
addRecipe("chocolate-pastry-cream", ["Dessert/Frosting/Custard"]);
addRecipe("chocolate-peanut-butter-frosting", ["Dessert/Frosting/Frosting"], true);
addRecipe("chocolate-peanut-butter-nice-cream", ["Dessert/Ice Cream"], true);
addRecipe("chocolate-peppermint-pizzelles", ["Dessert/Cookies/Pizzelles"]);
addRecipe("chocolate-pumpkin-cake", ["Dessert/Cake"]);
addRecipe("chocolate-pumpkin-cupcakes", ["Dessert/Cupcakes"]);
addRecipe("chocolate-truffles", ["Dessert/Candy"]);
addRecipe("churros", ["Dessert/Pastry"]);
addRecipe("cinnamon-bread-muffins", ["Dessert/Bread"]);
addRecipe("cinnamon-rolls", ["Dessert/Donuts"], true);
addRecipe("cinnamon-rolls-old", ["Dessert/Donuts"]);
addRecipe("coffee-pastry-cream", ["Dessert/Frosting/Custard"]);
addRecipe("cookie-dough-frosting", ["Dessert/Frosting/Frosting"]);
addRecipe("cookies-and-cream-fudge", ["Dessert/Fudge"]);
addRecipe("copycat-chick-fil-a-lemonade", ["Drink"], true);
addRecipe("cornbread-muffins", ["Dessert/Bread", "Dessert/Muffins"]);
addRecipe("cream-cheese-frosting", ["Dessert/Frosting/Frosting"], true);
addRecipe("cream-puffs", ["Dessert/Pastry"]);
addRecipe("dirty-rice", ["Main Dish"], true);
addRecipe("donut-glaze", ["Dessert/Donuts"]);
addRecipe("donuts", ["Dessert/Donuts"]);
addRecipe("double-chocolate-chip-cookies", ["Dessert/Cookies"], true);
addRecipe("double-chocolate-gelato", ["Dessert/Ice Cream"]);
addRecipe("easy-green-chicken-enchiladas", ["Main Dish"], true);
addRecipe("easy-slow-cooker-pulled-pork", ["Main Dish"], true);
addRecipe("eggnog-custard-pie", ["Dessert/Pie"]);
addRecipe("eggnog-fudge", ["Dessert/Fudge"]);
addRecipe("espresso-brownies", ["Dessert/Brownies"]);
addRecipe(
  "favorite-chocolate-buttercream",
  ["Dessert/Frosting/Frosting"],
  true,
);
addRecipe("fortune-cookies", ["Dessert/Cookies"]);
addRecipe("funnel-cake", ["Dessert/Donuts"]);
addRecipe("gelato", ["Dessert/Ice Cream"]);
addRecipe("ginger-snaps", ["Dessert/Cookies"]);
addRecipe("gingerbread-cookies", ["Dessert/Cookies"]);
addRecipe("grape-pie", ["Dessert/Pie"]);
addRecipe("hersheys-perfectly-chocolate-chocolate-cake", ["Dessert/Cake"], true);
addRecipe("hot-chocolate-cookies", ["Dessert/Cookies"], true);
addRecipe("ice-cream", ["Dessert/Ice Cream"]);
addRecipe("iced-gingerbread-oatmeal-cookies", ["Dessert/Cookies"], true);
addRecipe("key-lime-pie", ["Dessert/Pie"]);
addRecipe("kickin-cajun-seasoning-mix", ["Seasoning"], true);
addRecipe("lemon-cookies", ["Dessert/Cookies"]);
addRecipe("lemon-glaze", ["Dessert/Frosting/Icing"]);
addRecipe("lemon-lime-sorbet", ["Dessert/Ice Cream"]);
addRecipe("lemon-meringue-pie", ["Dessert/Pie"]);
addRecipe("lemon-pastry-cream", ["Dessert/Frosting/Custard"]);
addRecipe("lemon-poppyseed-bread", ["Dessert/Bread"]);
addRecipe("lime-sherbet", ["Dessert/Ice Cream"]);
addRecipe("maple-cream-cheese-frosting", ["Dessert/Frosting/Frosting"]);
addRecipe("maple-syrup-bread-muffins", ["Dessert/Bread"]);
addRecipe("maple-walnut-fudge", ["Dessert/Fudge"]);
addRecipe("marry-me-snickerdoodles", ["Dessert/Cookies"], true);
addRecipe("marshmallow-frosting", ["Dessert/Frosting/Frosting"]);
addRecipe("mascarpone-frosting", ["Dessert/Frosting/Frosting"]);
addRecipe("mashed-potatoes", ["Side Dish"], true);
addRecipe("mint-chocolate-fudge", ["Dessert/Fudge"]);
addRecipe("molasses-cookies", ["Dessert/Cookies"]);
addRecipe("monkey-bread", ["Dessert/Bread"]);
addRecipe("mrs-siggs-snickerdoodles", ["Dessert/Cookies"], true);
addRecipe("nanas-brownie-balls", ["Dessert/Candy"], true);
addRecipe("nanas-rocky-road-candies", ["Dessert/Candy"], true);
addRecipe("nutella-frosting", ["Dessert/Frosting/Frosting"]);
addRecipe("nutella-fudge", ["Dessert/Fudge"]);
addRecipe("oatmeal-raisin-cookies", ["Dessert/Cookies"]);
addRecipe("orange-brownies", ["Dessert/Brownies"]);
addRecipe("orange-cinnamon-swirl-bread-muffins", ["Dessert/Bread"]);
addRecipe("orange-creamsicle-fudge", ["Dessert/Fudge"]);
addRecipe("orange-pastry-cream", ["Dessert/Frosting/Custard"]);
addRecipe("orange-rolls", ["Dessert/Donuts"]);
addRecipe("oreo-graham-cracker-pie-crust", ["Dessert/Pie/Pie Crusts"]);
addRecipe("peach-pie", ["Dessert/Pie"]);
addRecipe("peanut-brittle", ["Dessert/Candy"]);
addRecipe("peanut-butter-chocolate-chip-bacon-cookies", ["Dessert/Cookies"]);
addRecipe("peanut-butter-cookies", ["Dessert/Cookies"]);
addRecipe("peanut-butter-frosting", ["Dessert/Frosting/Frosting"], true);
addRecipe("peanut-butter-fudge", ["Dessert/Fudge"]);
addRecipe("peanut-butter-pie", ["Dessert/Pie"]);
addRecipe("peanut-swirl-brownies", ["Dessert/Brownies"]);
addRecipe("pecan-pie", ["Dessert/Pie"]);
addRecipe("peppermint-bark", ["Dessert/Candy"]);
addRecipe("peppermint-cannolis", ["Dessert/Cannolis/Filling"]);
addRecipe("peppermint-glaze", ["Dessert/Frosting/Icing"]);
addRecipe("perfectly-chocolate-chocolate-frosting", ["Dessert/Frosting/Frosting"], true);
addRecipe("pie-crust", ["Dessert/Pie/Pie Crusts"]);
addRecipe("pineapple-cookies", ["Dessert/Cookies"]);
addRecipe("pineapple-pumpkin-bread-muffins", [
  "Dessert/Bread",
  "Dessert/Muffins",
]);
addRecipe("pinwheel-cookies", ["Dessert/Cookies"], true);
addRecipe("pizzelles", ["Dessert/Cookies/Pizzelles"]);
addRecipe("prime-rib", ["Main Dish"], true);
addRecipe("prime-rib-2", ["Main Dish"], true);
addRecipe("pumpkin-bread-muffins", ["Dessert/Bread", "Dessert/Muffins"]);
addRecipe("pumpkin-butterscotch-fudge", ["Dessert/Fudge"]);
addRecipe("pumpkin-cannolis", ["Dessert/Cannolis/Filling"]);
addRecipe("pumpkin-cheesecake-flavoring", ["Dessert/Cake/Cheesecake"]);
addRecipe("pumpkin-cupcakes", ["Dessert/Cupcakes"]);
addRecipe("pumpkin-donuts", ["Dessert/Donuts"]);
addRecipe("pumpkin-drop-cookies", ["Dessert/Cookies"]);
addRecipe("pumpkin-pastry-cream", ["Dessert/Frosting/Custard"]);
addRecipe("pumpkin-pie", ["Dessert/Pie"]);
addRecipe("pumpkin-spice-cake", ["Dessert/Cake"]);
addRecipe("pumpkin-whoopie-pies", ["Dessert/Cake/Whoopie Pies"]);
addRecipe("qdoba-queso-dip", ["Appetizer"], true);
addRecipe("qdoba-three-cheese-queso-copycat", ["Appetizer"], true);
addRecipe("rainbow-cookies", ["Dessert/Cookies"]);
addRecipe("raspberry-cheesecake-flavoring", ["Dessert/Cake/Cheesecake"]);
addRecipe("red-velvet-cupcakes", ["Dessert/Cupcakes"]);
addRecipe("red-velvet-fudge", ["Dessert/Fudge"]);
addRecipe("rice-krispie-treats", ["Dessert/Candy"], true);
addRecipe("rocky-road-fudge", ["Dessert/Fudge"]);
addRecipe("rule-of-3-garlic-buffalo-wing-sauce", ["Seasoning"], true);
addRecipe("sherbet", ["Dessert/Ice Cream"]);
addRecipe("shortbread-cookies", ["Dessert/Cookies"]);
addRecipe("snickerdoodles", ["Dessert/Cookies"]);
addRecipe("sorbet", ["Dessert/Ice Cream"]);
addRecipe("southwestern-egg-casserole", ["Breakfast"], true);
addRecipe("spicy-chicken-rigatoni", ["Main Dish"], true);
addRecipe("spritzgeback-cookies", ["Dessert/Cookies"]);
addRecipe("strawberry-rhubarb-pie", ["Dessert/Pie"]);
addRecipe("sugar-cookies", ["Dessert/Cookies"]);
addRecipe("sweet-corn-guacamole", ["Appetizer"], true);
addRecipe("sweet-potato-pie", ["Dessert/Pie"]);
addRecipe("texas-cinnamon-butter", ["Seasoning"], true);
addRecipe("texas-roadhouse-rolls", ["Side Dish"], true);
addRecipe("tiramisu", ["Dessert/Cake"]);
addRecipe("triple-chocolate-brownies", ["Dessert/Brownies"]);
addRecipe("twice-baked-potatoes", ["Side Dish"], true);
addRecipe("vanilla-buttercream-frosting", ["Dessert/Frosting/Frosting"]);
addRecipe("vanilla-cake", ["Dessert/Cake"]);
addRecipe("vanilla-frosting-whoopie-pie-filling", [
  "Dessert/Frosting/Frosting",
]);
addRecipe("vanilla-fudge", ["Dessert/Fudge"]);
addRecipe("vanilla-icing", ["Dessert/Frosting/Frosting"]);
addRecipe("vanilla-pastry-cream", ["Dessert/Frosting/Custard"]);
addRecipe("velveeta-fudge", ["Dessert/Fudge"]);
addRecipe("velveeta-hashbrown-casserole", ["Side Dish"], true);
addRecipe("watermelon-pie", ["Dessert/Pie"]);
addRecipe("white-chocolate-cheesecake", ["Dessert/Cake/Cheesecake"]);
addRecipe("whoopie-pies", ["Dessert/Cake/Whoopie Pies"]);

export default recipes;
