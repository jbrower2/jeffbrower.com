const CATEGORIES = new Set([
  "Appetizer",
  "Breakfast",
  "Collections/Girl Scout Cookies",
  "Dessert",
  "Dessert/Bread",
  "Dessert/Brownies",
  "Dessert/Cake",
  "Dessert/Cake/Cheesecake",
  "Dessert/Cake/Cheesecake/Shells",
  "Dessert/Cake/Whoopie Pies",
  "Dessert/Candy",
  "Dessert/Cannolis",
  "Dessert/Cannolis/Shells",
  "Dessert/Cookies",
  "Dessert/Cookies/Pizzelles",
  "Dessert/Cupcakes",
  "Dessert/Donuts",
  "Dessert/Frosting",
  "Dessert/Frosting/Custard",
  "Dessert/Frosting/Icing",
  "Dessert/Fudge",
  "Dessert/Ice Cream",
  "Dessert/Muffins",
  "Dessert/Pastry",
  "Dessert/Pie",
  "Dessert/Pie/Pie Crusts",
  "Drink",
  "Holidays/Fennelly Thanksgiving 2025",
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
addRecipe("alton-brown-sugar-cookies", ["Dessert/Cookies"], true);
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
addRecipe("best-damn-instant-pot-pork-tenderloin", ["Main Dish"], true);
addRecipe("biscotti", ["Dessert/Cookies"]);
addRecipe("black-and-white-cookies", ["Dessert/Cookies"]);
addRecipe("blackened-mahi-mahi", ["Main Dish"], true);
addRecipe("blackstone-chicken-fajitas", ["Main Dish"], true);
addRecipe("blackstone-fried-rice", ["Main Dish", "Side Dish"], true);
addRecipe("blonde-brownies", ["Dessert/Brownies"]);
addRecipe("blueberry-bread-muffins", ["Dessert/Bread", "Dessert/Muffins"]);
addRecipe("blueberry-pie", ["Dessert/Pie"]);
addRecipe("boston-cream", ["Dessert/Frosting/Custard"]);
addRecipe("brown-butter-frosting", ["Dessert/Frosting"]);
addRecipe("brown-butter-frosting-icing", ["Dessert/Frosting"]);
addRecipe("brown-sugar-glazed-salmon", ["Main Dish"], true);
addRecipe("brownies", ["Dessert/Brownies"], true);
addRecipe("butter-pecan-fudge", ["Dessert/Fudge"]);
addRecipe("butterbeer", ["Drink"], true);
addRecipe("butterbeer-old", ["Drink"]);
addRecipe("cake-batter-fudge", ["Dessert/Fudge"]);
addRecipe("candy-cane-fudge", ["Dessert/Fudge"]);
addRecipe("candy-corn", ["Dessert/Candy"]);
addRecipe("cannoli-filling", ["Dessert/Cannolis"]);
addRecipe("cannoli-shells", ["Dessert/Cannolis/Shells"]);
addRecipe("caramel-pecan-cheesecake", ["Dessert/Cake/Cheesecake", "Collections/Girl Scout Cookies"], true);
addRecipe("caramel-shortbread-cookies", ["Dessert/Cookies"]);
addRecipe("carrot-cake", ["Dessert/Cake"], true);
addRecipe("carrot-cake-cupcakes", ["Dessert/Cupcakes"], true);
addRecipe("cheesecake", ["Dessert/Cake/Cheesecake"]);
addRecipe("cheesecake-shell", ["Dessert/Cake/Cheesecake/Shells"]);
addRecipe("cheesy-hashbrown-casserole", ["Side Dish"], true);
addRecipe(
  "cheesy-hasselback-potato-gratin",
  ["Side Dish", "Holidays/Fennelly Thanksgiving 2025"],
  true,
);
addRecipe("cherry-banana-bread-muffins", ["Dessert/Bread", "Dessert/Muffins"]);
addRecipe("cherry-pie", ["Dessert/Pie"]);
addRecipe(
  "chewy-double-chocolate-peppermint-cookies",
  ["Dessert/Cookies"],
  true,
);
addRecipe("chili", ["Main Dish"], true);
addRecipe("chocolate-brownies", ["Dessert/Brownies"]);
addRecipe("chocolate-buttercream-frosting", ["Dessert/Frosting"]);
addRecipe("chocolate-cake", ["Dessert/Cake"]);
addRecipe("chocolate-cannoli-shells", ["Dessert/Cannolis/Shells"]);
addRecipe("chocolate-cannolis", ["Dessert/Cannolis"]);
addRecipe("chocolate-cheesecake", ["Dessert/Cake/Cheesecake"]);
addRecipe("chocolate-chip-cinnamon-pizzelles", ["Dessert/Cookies/Pizzelles"]);
addRecipe("chocolate-chip-cookie-dough-fudge", ["Dessert/Fudge"]);
addRecipe("chocolate-chip-cookies", ["Dessert/Cookies"]);
addRecipe("chocolate-chip-cupcakes", ["Dessert/Cupcakes"]);
addRecipe("chocolate-chocolate-chip-cookies", ["Dessert/Cookies"], true);
addRecipe("chocolate-chocolate-chip-cookies-old", ["Dessert/Cookies"]);
addRecipe("chocolate-cinnamon-fudge", ["Dessert/Fudge"]);
addRecipe("chocolate-coconut-chantilly-pie", ["Dessert/Pie", "Collections/Girl Scout Cookies"], true);
addRecipe("chocolate-covered-pretzels", ["Dessert/Candy"]);
addRecipe("chocolate-crepes", ["Breakfast"], true);
addRecipe("chocolate-crinkle-cookies", ["Dessert/Cookies"], true);
addRecipe("chocolate-cream-pie", ["Dessert/Pie"]);
addRecipe("chocolate-donuts", ["Dessert/Donuts"]);
addRecipe("chocolate-eclairs", ["Dessert/Pastry"]);
addRecipe("chocolate-fudge", ["Dessert/Fudge"]);
addRecipe("chocolate-hazelnut-parfaits", ["Dessert", "Collections/Girl Scout Cookies"], true);
addRecipe("chocolate-icing", ["Dessert/Frosting/Icing"]);
addRecipe("chocolate-mug-cake", ["Dessert/Cake"], true);
addRecipe("chocolate-orange-fudge", ["Dessert/Fudge"]);
addRecipe("chocolate-pastry-cream", ["Dessert/Frosting/Custard"]);
addRecipe("chocolate-peanut-butter-frosting", ["Dessert/Frosting"], true);
addRecipe("chocolate-peanut-butter-nice-cream", ["Dessert/Ice Cream"], true);
addRecipe("chocolate-peppermint-pizzelles", ["Dessert/Cookies/Pizzelles"]);
addRecipe(
  "chocolate-pumpkin-cake-and-cupcakes",
  ["Dessert/Cake", "Dessert/Cupcakes"],
  true,
);
addRecipe("chocolate-truffles", ["Dessert/Candy"]);
addRecipe("churros", ["Dessert/Pastry"]);
addRecipe("cinnamon-bread-muffins", ["Dessert/Bread"]);
addRecipe("cinnamon-rolls", ["Dessert/Donuts"], true);
addRecipe("cinnamon-rolls-old", ["Dessert/Donuts"]);
addRecipe("coffee-pastry-cream", ["Dessert/Frosting/Custard"]);
addRecipe("cookie-dough-frosting", ["Dessert/Frosting"]);
addRecipe("cookie-toffee-nut-bark", ["Dessert/Candy", "Collections/Girl Scout Cookies"], true);
addRecipe("cookies-and-cream-fudge", ["Dessert/Fudge"]);
addRecipe("copycat-chick-fil-a-lemonade", ["Drink"], true);
addRecipe("cornbread-muffins", ["Dessert/Bread", "Dessert/Muffins"]);
addRecipe("cream-cheese-frosting", ["Dessert/Frosting"], true);
addRecipe("cream-puffs", ["Dessert/Pastry"]);
addRecipe("crepes", ["Breakfast"], true);
addRecipe("crushed-red-pepper-hummus", ["Appetizer"], true);
addRecipe("dark-chocolate-candy-cane-cookies", ["Dessert/Cookies"], true);
addRecipe("delightful-caramel-bars", ["Dessert/Brownies", "Collections/Girl Scout Cookies"], true);
addRecipe("dirty-rice", ["Main Dish"], true);
addRecipe("do-si-dos-banana-pudding", ["Dessert", "Collections/Girl Scout Cookies"], true);
addRecipe("do-si-dos-candy-bars", ["Dessert/Candy", "Collections/Girl Scout Cookies"], true);
addRecipe("donut-glaze", ["Dessert/Donuts"]);
addRecipe("donuts", ["Dessert/Donuts"]);
addRecipe("double-chocolate-chip-cookies", ["Dessert/Cookies"], true);
addRecipe("double-chocolate-gelato", ["Dessert/Ice Cream"]);
addRecipe("dulce-delites", ["Dessert/Brownies", "Collections/Girl Scout Cookies"], true);
addRecipe(
  "easy-gravy",
  ["Seasoning", "Holidays/Fennelly Thanksgiving 2025"],
  true,
);
addRecipe("easy-green-chicken-enchiladas", ["Main Dish"], true);
addRecipe("easy-slow-cooker-pulled-pork", ["Main Dish"], true);
addRecipe("eggnog-custard-pie", ["Dessert/Pie"]);
addRecipe("eggnog-fudge", ["Dessert/Fudge"]);
addRecipe("espresso-brownies", ["Dessert/Brownies"]);
addRecipe("fantastic-toffee-tastic-cheesecake", ["Dessert/Cake/Cheesecake", "Collections/Girl Scout Cookies"], true);
addRecipe("favorite-chocolate-buttercream", ["Dessert/Frosting"], true);
addRecipe("festive-white-chocolate-cheesecake", ["Dessert/Cake/Cheesecake", "Collections/Girl Scout Cookies"], true);
addRecipe("fortune-cookies", ["Dessert/Cookies"]);
addRecipe("frozen-raspberry-cheesecakes", ["Dessert/Cake/Cheesecake", "Collections/Girl Scout Cookies"], true);
addRecipe("funnel-cake", ["Dessert/Donuts"]);
addRecipe("gelato", ["Dessert/Ice Cream"]);
addRecipe("german-chocolate-ice-cream-cookie-torte", ["Dessert/Ice Cream", "Collections/Girl Scout Cookies"], true);
addRecipe("ginger-snaps", ["Dessert/Cookies"]);
addRecipe("gingerbread", ["Dessert/Bread"], true);
addRecipe("gingerbread-cookies", ["Dessert/Cookies"]);
addRecipe("gingerbread-men-smores", ["Dessert/Cookies"], true);
addRecipe("girl-scout-bridging-bars", ["Dessert/Brownies", "Collections/Girl Scout Cookies"], true);
addRecipe("grams-banana-bread", ["Dessert/Bread"], true);
addRecipe("grape-pie", ["Dessert/Pie"]);
addRecipe(
  "hersheys-perfectly-chocolate-chocolate-cake",
  ["Dessert/Cake"],
  true,
);
addRecipe("hot-chocolate-cookies", ["Dessert/Cookies"], true);
addRecipe("ice-cream", ["Dessert/Ice Cream"]);
addRecipe("iced-gingerbread-oatmeal-cookies", ["Dessert/Cookies"], true);
addRecipe("key-lime-pie", ["Dessert/Pie"]);
addRecipe("kickin-cajun-seasoning-mix", ["Seasoning"], true);
addRecipe("kings-hawaiian-french-toast", ["Breakfast"], true);
addRecipe("lemon-blueberry-crunch-cake", ["Dessert/Cake", "Collections/Girl Scout Cookies"], true);
addRecipe("lemon-cookies", ["Dessert/Cookies"]);
addRecipe("lemon-glaze", ["Dessert/Frosting/Icing"]);
addRecipe("lemon-lime-sorbet", ["Dessert/Ice Cream"]);
addRecipe("lemon-meringue-pie", ["Dessert/Pie"]);
addRecipe("lemon-pastry-cream", ["Dessert/Frosting/Custard"]);
addRecipe("lemon-poppyseed-bread", ["Dessert/Bread"]);
addRecipe("lemon-shortbread-cheesecake", ["Dessert/Cake/Cheesecake", "Collections/Girl Scout Cookies"], true);
addRecipe("lemon-surprise-cheesecake", ["Dessert/Cake/Cheesecake", "Collections/Girl Scout Cookies"], true);
addRecipe("lime-sherbet", ["Dessert/Ice Cream"]);
addRecipe("maple-cream-cheese-frosting", ["Dessert/Frosting"]);
addRecipe("maple-syrup-bread-muffins", ["Dessert/Bread"]);
addRecipe("maple-walnut-fudge", ["Dessert/Fudge"]);
addRecipe("marry-me-snickerdoodles", ["Dessert/Cookies"], true);
addRecipe("marshmallow-frosting", ["Dessert/Frosting"]);
addRecipe("mascarpone-frosting", ["Dessert/Frosting"]);
addRecipe(
  "mashed-potatoes",
  ["Side Dish", "Holidays/Fennelly Thanksgiving 2025"],
  true,
);
addRecipe(
  "mashed-sweet-potatoes",
  ["Side Dish", "Holidays/Fennelly Thanksgiving 2025"],
  true,
);
addRecipe("mile-high-peppermint-pie", ["Dessert/Pie", "Collections/Girl Scout Cookies"], true);
addRecipe("mini-thin-mints-mocha-ice-cream-sandwiches", ["Dessert/Ice Cream", "Collections/Girl Scout Cookies"], true);
addRecipe("mint-chocolate-fudge", ["Dessert/Fudge"]);
addRecipe("molasses-cookies", ["Dessert/Cookies"]);
addRecipe("mollys-mini-lemon-shortbread-puddings", ["Dessert", "Collections/Girl Scout Cookies"], true);
addRecipe("monkey-bread", ["Dessert/Bread"]);
addRecipe("mrs-siggs-snickerdoodles", ["Dessert/Cookies"], true);
addRecipe("nanas-brownie-balls", ["Dessert/Candy"], true);
addRecipe("nanas-rocky-road-candies", ["Dessert/Candy"], true);
addRecipe("neapolitan-dough", ["Main Dish"], true);
addRecipe("nutella-frosting", ["Dessert/Frosting"]);
addRecipe("nutella-fudge", ["Dessert/Fudge"]);
addRecipe("nutty-caramel-turtles", ["Dessert/Candy", "Collections/Girl Scout Cookies"], true);
addRecipe("oatmeal-raisin-cookies", ["Dessert/Cookies"]);
addRecipe("orange-brownies", ["Dessert/Brownies"]);
addRecipe("orange-cinnamon-swirl-bread-muffins", ["Dessert/Bread"]);
addRecipe("orange-cream-cheese-frosting", ["Dessert/Frosting"], true);
addRecipe("orange-creamsicle-fudge", ["Dessert/Fudge"]);
addRecipe("orange-julius", ["Drink"], true);
addRecipe("orange-pastry-cream", ["Dessert/Frosting/Custard"]);
addRecipe("orange-rolls", ["Dessert/Donuts"]);
addRecipe("oreo-coal", ["Dessert"], true);
addRecipe("oreo-graham-cracker-pie-crust", ["Dessert/Pie/Pie Crusts"]);
addRecipe("peach-pie", ["Dessert/Pie"]);
addRecipe("peanut-brittle", ["Dessert/Candy"]);
addRecipe("peanut-butter-balls", ["Dessert/Cookies"], true);
addRecipe("peanut-butter-chocolate-chip-bacon-cookies", ["Dessert/Cookies"]);
addRecipe("peanut-butter-cookie-crunch-clusters", ["Dessert/Candy", "Collections/Girl Scout Cookies"], true);
addRecipe("peanut-butter-cookie-parfait", ["Dessert", "Collections/Girl Scout Cookies"], true);
addRecipe("peanut-butter-cookies", ["Dessert/Cookies"]);
addRecipe("peanut-butter-cream-dessert", ["Dessert", "Collections/Girl Scout Cookies"], true);
addRecipe("peanut-butter-cup-stuffed-cookies", ["Dessert/Cookies"], true);
addRecipe("peanut-butter-frosting", ["Dessert/Frosting"], true);
addRecipe("peanut-butter-fudge", ["Dessert/Fudge"]);
addRecipe("peanut-butter-icebox-dessert", ["Dessert", "Collections/Girl Scout Cookies"], true);
addRecipe("peanut-butter-pie", ["Dessert/Pie"]);
addRecipe("peanut-butter-trail-mix-fudge", ["Dessert/Fudge", "Collections/Girl Scout Cookies"], true);
addRecipe("peanut-caramel-thumbprint-no-bake-cookies", ["Dessert/Cookies", "Collections/Girl Scout Cookies"], true);
addRecipe("peanut-swirl-brownies", ["Dessert/Brownies"]);
addRecipe("pecan-pie", ["Dessert/Pie"]);
addRecipe("peppermint-bark", ["Dessert/Candy"]);
addRecipe("peppermint-cannolis", ["Dessert/Cannolis"]);
addRecipe("peppermint-chip-cheesecake", ["Dessert/Cake/Cheesecake", "Collections/Girl Scout Cookies"], true);
addRecipe("peppermint-glaze", ["Dessert/Frosting/Icing"]);
addRecipe(
  "peppermint-pattie-stuffed-chocolate-cookies",
  ["Dessert/Cookies"],
  true,
);
addRecipe("perfectly-chocolate-chocolate-frosting", ["Dessert/Frosting"], true);
addRecipe("pie-crust", ["Dessert/Pie/Pie Crusts"]);
addRecipe("pineapple-cookies", ["Dessert/Cookies"]);
addRecipe("pineapple-pumpkin-bread-muffins", [
  "Dessert/Bread",
  "Dessert/Muffins",
]);
addRecipe("pinwheel-cookies", ["Dessert/Cookies"], true);
addRecipe("pizza-sauce", ["Main Dish"], true);
addRecipe("pizzelles", ["Dessert/Cookies/Pizzelles"]);
addRecipe("prime-rib", ["Main Dish"], true);
addRecipe("prime-rib-2", ["Main Dish"], true);
addRecipe("pumpkin-bread-muffins", ["Dessert/Bread", "Dessert/Muffins"]);
addRecipe("pumpkin-butterscotch-fudge", ["Dessert/Fudge"]);
addRecipe("pumpkin-cannolis", ["Dessert/Cannolis"]);
addRecipe("pumpkin-cheesecake-flavoring", ["Dessert/Cake/Cheesecake"]);
addRecipe("pumpkin-cupcakes", ["Dessert/Cupcakes"]);
addRecipe("pumpkin-donuts", ["Dessert/Donuts"]);
addRecipe("pumpkin-drop-cookies", ["Dessert/Cookies"], true);
addRecipe("pumpkin-pastry-cream", ["Dessert/Frosting/Custard"]);
addRecipe("pumpkin-pie", ["Dessert/Pie"]);
addRecipe("pumpkin-spice-cake", ["Dessert/Cake"]);
addRecipe("pumpkin-whoopie-pies", ["Dessert/Cake/Whoopie Pies"]);
addRecipe("qdoba-queso-dip", ["Appetizer"], true);
addRecipe("qdoba-three-cheese-queso-copycat", ["Appetizer"], true);
addRecipe("rainbow-cookies", ["Dessert/Cookies"]);
addRecipe("raspberry-cheesecake-flavoring", ["Dessert/Cake/Cheesecake"]);
addRecipe("raspberry-lemonades-bread-pudding", ["Dessert", "Collections/Girl Scout Cookies"], true);
addRecipe("raspberry-thumbprint-cookies", ["Dessert/Cookies"], true);
addRecipe("red-velvet-crinkle-cookies", ["Dessert/Cookies"], true);
addRecipe("red-velvet-cupcakes", ["Dessert/Cupcakes"]);
addRecipe("red-velvet-fudge", ["Dessert/Fudge"]);
addRecipe("reeses-stuffed-peanut-butter-cookies", ["Dessert/Cookies"], true);
addRecipe("rice-krispie-treats", ["Dessert/Candy"], true);
addRecipe("rivers-banana-bread", ["Dessert/Bread"], true);
addRecipe("rocky-road-fudge", ["Dessert/Fudge"]);
addRecipe("rule-of-3-garlic-buffalo-wing-sauce", ["Seasoning"], true);
addRecipe("salsa", ["Seasoning"], true);
addRecipe("salsa-morada", ["Seasoning"], true);
addRecipe("salt-baked-potatoes", ["Side Dish"], true);
addRecipe("samoa-toffee", ["Dessert/Candy", "Collections/Girl Scout Cookies"], true);
addRecipe("samoas-swirl-no-churn-ice-cream", ["Dessert/Ice Cream", "Collections/Girl Scout Cookies"], true);
addRecipe("sherbet", ["Dessert/Ice Cream"]);
addRecipe("shortbread-cookies", ["Dessert/Cookies"]);
addRecipe("shortbread-fudge-tiramisu", ["Dessert/Cake", "Collections/Girl Scout Cookies"], true);
addRecipe("shortbread-trefoils-toffee-chocolate-bark", ["Dessert/Candy", "Collections/Girl Scout Cookies"], true);
addRecipe(
  "simple-whole-roast-turkey",
  ["Main Dish", "Holidays/Fennelly Thanksgiving 2025"],
  true,
);
addRecipe("smores-frosted-crispy-bars", ["Dessert/Brownies", "Collections/Girl Scout Cookies"], true);
addRecipe("smores-ice-cream", ["Dessert/Ice Cream", "Collections/Girl Scout Cookies"], true);
addRecipe("smores-peanut-butter-pudgy-pie", ["Dessert", "Collections/Girl Scout Cookies"], true);
addRecipe("smores-summertime-cheesecake", ["Dessert/Cake/Cheesecake", "Collections/Girl Scout Cookies"], true);
addRecipe("snickerdoodle-cookie-dough-truffles", ["Dessert/Cookies"], true);
addRecipe("snickerdoodles", ["Dessert/Cookies"]);
addRecipe("soft-chocolate-chip-cookies", ["Dessert/Cookies"], true);
addRecipe("sorbet", ["Dessert/Ice Cream"]);
addRecipe("southwestern-egg-casserole", ["Breakfast"], true);
addRecipe("spicy-chicken-rigatoni", ["Main Dish"], true);
addRecipe("spritzgeback-cookies", ["Dessert/Cookies"]);
addRecipe("strawberry-rhubarb-pie", ["Dessert/Pie"]);
addRecipe("sugar-cookies", ["Dessert/Cookies"]);
addRecipe("sunday-sin-cake", ["Dessert/Cake", "Collections/Girl Scout Cookies"], true);
addRecipe("sweet-corn-guacamole", ["Appetizer"], true);
addRecipe("sweet-potato-pie", ["Dessert/Pie"]);
addRecipe("texas-cinnamon-butter", ["Seasoning"], true);
addRecipe("texas-roadhouse-rolls", ["Side Dish"], true);
addRecipe("thin-mints-cupcakes", ["Dessert/Cupcakes", "Collections/Girl Scout Cookies"], true);
addRecipe("thin-mints-popcorn", ["Dessert/Candy", "Collections/Girl Scout Cookies"], true);
addRecipe("thin-mints-white-chocolate-biscotti", ["Dessert/Cookies", "Collections/Girl Scout Cookies"], true);
addRecipe(
  "tinis-famous-mac-and-cheese",
  ["Main Dish", "Holidays/Fennelly Thanksgiving 2025"],
  true,
);
addRecipe("tiramisu", ["Dessert/Cake"]);
addRecipe("toll-house-chocolate-chip-cookies", ["Dessert/Cookies"], true);
addRecipe("touch-of-coconut-baklava", ["Dessert/Pastry", "Collections/Girl Scout Cookies"], true);
addRecipe("triple-chocolate-brownies", ["Dessert/Brownies"]);
addRecipe("twice-baked-potatoes", ["Side Dish"], true);
addRecipe("vanilla-buttercream-frosting", ["Dessert/Frosting"]);
addRecipe("vanilla-cake", ["Dessert/Cake"]);
addRecipe("vanilla-frosting-whoopie-pie-filling", ["Dessert/Frosting"]);
addRecipe("vanilla-fudge", ["Dessert/Fudge"]);
addRecipe("vanilla-icing", ["Dessert/Frosting"]);
addRecipe("vanilla-pastry-cream", ["Dessert/Frosting/Custard"]);
addRecipe("velveeta-fudge", ["Dessert/Fudge"]);
addRecipe("velveeta-hashbrown-casserole", ["Side Dish"], true);
addRecipe("watermelon-pie", ["Dessert/Pie"]);
addRecipe("white-chocolate-cheesecake", ["Dessert/Cake/Cheesecake"]);
addRecipe("whoopie-pies", ["Dessert/Cake/Whoopie Pies"]);

export default recipes;
