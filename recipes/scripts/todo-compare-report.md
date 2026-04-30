# Todo folder ↔ current recipes

- Converted files: 21
- STRICT: 0
- SUBSET: 1
- DIVERGENT: 6
- NEW: 13
- REFERENCE: 1
- MISSING_FILE: 0

Classification:
- **STRICT** — ingredients and instructions match line-for-line (post-normalization, same order).
- **SUBSET** — every converted line appears in current; current may have added notes/extra steps.
- **DIVERGENT** — at least one converted line is NOT in the current recipe. The recipes differ.
- **NEW** — converted represents a recipe we don't have in the app.
- **REFERENCE** — source file is not a single recipe (e.g. multi-recipe summary).

## Summary

No todo-folder source matches its current-recipe counterpart word-for-word. Automated DIVERGENT flags mostly reflect cosmetic edits (Title Case ingredient names, combined multi-sentence steps, "°F" vs "degrees F") but a few are **substantive recipe changes**:

### Substantive ingredient / quantity differences

- **Pumpkin Cookies → pumpkin-drop-cookies.md:** allspice reduced from **{1} tsp → {1/4} tsp** and nutmeg reduced from **{1} tsp → {1/4} tsp**. The current matches the Betty Crocker source; the source PDF in `todo/` is a spicier variant.
- **Chocolate Pumpkin Cake → chocolate-pumpkin-cake.md / chocolate-pumpkin-cupcakes.md:** current recipe is a **scaled-down, re-proportioned version** of the source (not a linear scale). Source: `2 1/2 cup + 2 tbsp` flour, `1 cup + 2 tbsp` cocoa, `5` eggs, `2 1/4` sticks butter, `3/4 cup` buttermilk, `1 1/2 cup` each of dark brown + granulated sugar. Current cake and cupcakes: `1 3/4 cup` flour, `3/4 cup` cocoa, `3` eggs, `1 1/2` stick butter, `1/2 cup` buttermilk, `1 cup` each of brown + white sugar. Cinnamon and nutmeg were also halved (`2 1/4 tsp` → `1/2 tbsp`, `3/4 tsp` → `1/2 tsp`). The source also uses "Orange Cream-Cheese Frosting" explicitly; current just says "Frosting".
- **Double Chocolate Chip Cookies → double-chocolate-chip-cookies.md:** current adds **{1 1/2} tsp cornstarch** and increases chill time from **2 hrs → 3 hrs**. Same formula otherwise; current adds gram measurements and a freezing note.

### Cosmetic / minor differences (same recipe)

- **dirty rice → dirty-rice.md:** `Zatarians` → `Zatarain's` (apostrophe/spelling) and `{3} tbsp butter` → `{3} tbsp butter, divided`. Otherwise identical.
- **Mrs. Sigg's Snickerdoodles → mrs-siggs-snickerdoodles.md:** same recipe; reformatted into labeled sub-steps (`**Make cookies:**`, `**Make cinnamon-sugar:**`), `eggs` → `large eggs`, `degrees F` → `°F`, added "switching racks halfway through" and intro blurb.
- **Raspberry and Almond Shortbread Thumbprints → raspberry-thumbprint-cookies.md:** same recipe; the two almond-extract lines (`{1/2}` + `{3/4}`) were collapsed into one `{1 1/4} teaspoons almond extract, divided` and instructions refer to portions with `{...}` tokens.

### Flavors → ice-cream.md

The `Flavors.xlsx` is an ice-cream flavor-addition table; the current `ice-cream.md` wraps the same flavor list with a base-custard recipe and per-flavor `### ` sections. The flavor list (bases + compounds) is preserved in current.

### Not in the app

Sources without a matching current recipe: Brownies, chili, Award-Winning Soft Chocolate Chip Cookies (pudding-mix variant), Crushed Red Pepper Hummus, Dark Chocolate Candy Cane Cookies, Gingerbread (a different formula from the current `gingerbread-cookies.md`), Neapolitan Dough, Pizza Sauce, Red Velvet Crinkle Cookies, Reese's Stuffed Peanut Butter Cookies, Salsa (the plain recipe; `salsa-morada` is a different Buena Mulata pepper recipe), Sugar Cookies (Alton Brown variant, uses milk instead of the buttermilk in current), Yellow Cake.

### Reference

- `Recipes.xlsx` is a cross-recipe totals spreadsheet listing ingredient quantities across 9 cookie recipes; not convertible to a single recipe.

## STRICT (0)

_None._

## SUBSET (1)

### Flavors.md → ice-cream.md [title differs: "Ice Cream Flavors" vs "Ice Cream"]
- Counts — converted: 0 ing / 0 ins; current: 7 ing / 16 ins
- Per-slug category: **SUBSET**
- **Extra in current (current has, converted does not):**
  - `{1} cup Milk, whole`
  - `{3/4} cup Sugar`
  - `{2} cup Heavy Cream`
  - `{1/16} tsp Salt`
  - `{1} Vanilla Bean, split lengthwise`
  - `{6} Egg Yolk`
  - `{3/4} tsp Vanilla Extract`
- **Extra instructions in current:**
  - `Warm the milk, sugar, 1 cup of the heavy cream and the salt in a medium saucepan over low heat, stirring until the sugar is dissolved`
  - `Scrape the seeds from the vanilla bean into the milk mixture and add the bean to the mixture as well`
  - `Cover, remove from the heat and let steep at room temperature for 30 minutes`
  - `Pour the remaining 1 cup heavy cream into a large bowl and place a fine-mesh sieve on top`
  - `Whisk the egg yolks in a medium bowl`
  - `Slowly pour the warmed milk mixture into the egg yolks, whisking constantly`
  - `Scrape the mixture back into the saucepan`
  - `Place the saucepan over medium heat and stir constantly with a rubber spatula, being sure to scrape the bottom of the pan as you stir, until the mixture thickens and coats the back of the spatula, a few minutes`
  - `The mixture should register 170 to 175 degrees F on an instant-read digital thermometer`
  - `Pour the custard through the fine-mesh sieve and stir it into the cream`
  - `Add in additional ingredients`
  - `Place the vanilla bean into the custard, stir in the vanilla extract, and place the bowl over an ice bath`
  - `Stir occasionally, until the mixture is cool`
  - `Cover and transfer the custard to the refrigerator until completely chilled, at least 8 hours or overnight`
  - `When ready to churn the ice cream, remove the vanilla bean from the custard and freeze the mixture in your ice cream maker according to the manufacturer's instructions`
  - `Transfer to a freezer-safe container and store in the freezer`

## DIVERGENT (6)

### Chocolate Pumpkin Cake and Cupcakes Recipe.md → chocolate-pumpkin-cake.md [title differs: "Chocolate Pumpkin Cake and Cupcakes" vs "Chocolate Pumpkin Cake"]
- Counts — converted: 16 ing / 5 ins; current: 14 ing / 17 ins
- Per-slug category: **DIVERGENT**
- **Missing in current (converted has, current does not):**
  - `{2 1/2} cup(s) all-purpose flour`
  - `{2} tablespoon(s) all-purpose flour`
  - `{1} cup(s) good-quality cocoa`
  - `{2} tablespoon(s) good-quality cocoa`
  - `{1} tablespoon(s) baking powder`
  - `{1 1/2} teaspoon(s) baking soda`
  - `{2 1/4} teaspoon(s) ground cinnamon`
  - `{3/4} teaspoon(s) fresh-grated nutmeg`
  - `{3/4} cup(s) buttermilk`
  - `{1 1/2} cup(s) pumpkin purée`
  - `{1 1/2} teaspoon(s) vanilla extract`
  - `{2 1/4} stick(s) unsalted butter, softened`
  - `{1 1/2} cup(s) (firmly packed) dark brown sugar`
  - `{1 1/2} cup(s) granulated sugar`
  - `{5} large eggs`
  - `Orange Cream-Cheese Frosting`
- **Missing instructions in current:**
  - `Prepare cake pans: Heat oven to 350 degrees F. Lightly butter three 8-inch cake pans and fit each bottom with an 8-inch circle of parchment paper. Lightly butter the parchment paper. Set aside.`
  - `Make the batter: Sift the flour, cocoa, baking powder, baking soda, cinnamon, and nutmeg in a large bowl and set aside. Combine the buttermilk, pumpkin, and vanilla in a medium bowl and set aside. Beat the butter and sugar together in a large bowl, with an electric mixer set on medium speed, until fluffy. Add the eggs, one at a time, beating well after each addition, until the mixture is smooth and light. Alternately add the flour mixture and buttermilk mixture, blending well after each addition.`
  - `Bake the cake: Divide the batter among the pans and bake until a wooden skewer inserted into the middle comes out clean -- about 35 minutes. Cool the cakes in the pan for 20 minutes. Remove cakes and cool. (For cupcakes: Heat oven to 375 degrees F. Place cupcake liners in standard cupcake tins and fill each with 1/4 cup of batter. Bake for 22 minutes.)`
  - `Assemble the cake: Trim each of the layers. Place one layer on a cake plate and top with one third of the frosting. Repeat with the second and third layers. (To ensure that the cake layers do not shift, cut three skewers to 1/4 inch shorter than the full height of the cake and insert them before icing the top layer.) Refrigerate until ready to serve.`
  - `Make our Orange Cream-Cheese Frosting.`
- **Extra in current (current has, converted does not):**
  - `{1 3/4} cup All-purpose Flour`
  - `{3/4} cup Unsweetened Cocoa Powder`
  - `{2} tsp Baking Powder`
  - `{1} tsp Baking Soda`
  - `{1/2} tbsp Cinnamon`
  - `{1/2} tsp Nutmeg`
  - `{1/2} cup Buttermilk`
  - `{1} cup Pumpkin Puree`
  - `{1} tsp Vanilla Extract`
  - `{1 1/2} stick Butter, softened`
  - `{1} cup Brown Sugar`
  - `{1} cup Sugar`
  - `{3} Egg`
  - `Frosting`
- **Extra instructions in current:**
  - `Heat oven to 350 degrees F`
  - `Lightly butter three 8-inch cake pans and fit each bottom with an 8-inch circle of parchment paper`
  - `Lightly butter the parchment paper`
  - `Set aside`
  - `Sift the flour, cocoa, baking powder, baking soda, cinnamon, and nutmeg in a large bowl and set aside`
  - `Combine the buttermilk, pumpkin, and vanilla in a medium bowl and set aside`
  - `Beat the butter and sugars together in a large bowl, with an electric mixer set on medium speed, until fluffy`
  - `Add the eggs, one at a time, beating well after each addition, until the mixture is smooth and light`
  - `Alternately add the flour mixture and buttermilk mixture, blending well after each addition`
  - `Divide the batter among the pans and bake about 35 minutes until a wooden skewer inserted into the middle comes out clean`
  - `Cool the cakes in the pan for 20 minutes`
  - `Remove cakes and cool`
  - `Trim each of the layers`
  - `Place one layer on a cake plate and top with one third of the frosting`
  - `Repeat with the second and third layers`
  - `To ensure that the cake layers do not shift, cut three skewers to 1/4 inch shorter than the full height of the cake and insert them before icing the top layer`
  - `Refrigerate until ready to serve`

### Chocolate Pumpkin Cake and Cupcakes Recipe.md → chocolate-pumpkin-cupcakes.md [title differs: "Chocolate Pumpkin Cake and Cupcakes" vs "Chocolate Pumpkin Cupcakes"]
- Counts — converted: 16 ing / 5 ins; current: 14 ing / 12 ins
- Per-slug category: **DIVERGENT**
- **Missing in current (converted has, current does not):**
  - `{2 1/2} cup(s) all-purpose flour`
  - `{2} tablespoon(s) all-purpose flour`
  - `{1} cup(s) good-quality cocoa`
  - `{2} tablespoon(s) good-quality cocoa`
  - `{1} tablespoon(s) baking powder`
  - `{1 1/2} teaspoon(s) baking soda`
  - `{2 1/4} teaspoon(s) ground cinnamon`
  - `{3/4} teaspoon(s) fresh-grated nutmeg`
  - `{3/4} cup(s) buttermilk`
  - `{1 1/2} cup(s) pumpkin purée`
  - `{1 1/2} teaspoon(s) vanilla extract`
  - `{2 1/4} stick(s) unsalted butter, softened`
  - `{1 1/2} cup(s) (firmly packed) dark brown sugar`
  - `{1 1/2} cup(s) granulated sugar`
  - `{5} large eggs`
  - `Orange Cream-Cheese Frosting`
- **Missing instructions in current:**
  - `Prepare cake pans: Heat oven to 350 degrees F. Lightly butter three 8-inch cake pans and fit each bottom with an 8-inch circle of parchment paper. Lightly butter the parchment paper. Set aside.`
  - `Make the batter: Sift the flour, cocoa, baking powder, baking soda, cinnamon, and nutmeg in a large bowl and set aside. Combine the buttermilk, pumpkin, and vanilla in a medium bowl and set aside. Beat the butter and sugar together in a large bowl, with an electric mixer set on medium speed, until fluffy. Add the eggs, one at a time, beating well after each addition, until the mixture is smooth and light. Alternately add the flour mixture and buttermilk mixture, blending well after each addition.`
  - `Bake the cake: Divide the batter among the pans and bake until a wooden skewer inserted into the middle comes out clean -- about 35 minutes. Cool the cakes in the pan for 20 minutes. Remove cakes and cool. (For cupcakes: Heat oven to 375 degrees F. Place cupcake liners in standard cupcake tins and fill each with 1/4 cup of batter. Bake for 22 minutes.)`
  - `Assemble the cake: Trim each of the layers. Place one layer on a cake plate and top with one third of the frosting. Repeat with the second and third layers. (To ensure that the cake layers do not shift, cut three skewers to 1/4 inch shorter than the full height of the cake and insert them before icing the top layer.) Refrigerate until ready to serve.`
  - `Make our Orange Cream-Cheese Frosting.`
- **Extra in current (current has, converted does not):**
  - `{1 3/4} cup All-purpose Flour`
  - `{3/4} cup Unsweetened Cocoa Powder`
  - `{2} tsp Baking Powder`
  - `{1} tsp Baking Soda`
  - `{1/2} tbsp Cinnamon`
  - `{1/2} tsp Nutmeg`
  - `{1/2} cup Buttermilk`
  - `{1} cup Pumpkin Puree`
  - `{1} tsp Vanilla Extract`
  - `{1 1/2} stick Butter, softened`
  - `{1} cup Brown Sugar`
  - `{1} cup Sugar`
  - `{3} Egg`
  - `Frosting`
- **Extra instructions in current:**
  - `Heat oven to 375 degrees F`
  - `Place cupcake liners in standard cupcake tins`
  - `Set aside`
  - `Sift the flour, cocoa, baking powder, baking soda, cinnamon, and nutmeg in a large bowl and set aside`
  - `Combine the buttermilk, pumpkin, and vanilla in a medium bowl and set aside`
  - `Beat the butter and sugars together in a large bowl, with an electric mixer set on medium speed, until fluffy`
  - `Add the eggs, one at a time, beating well after each addition, until the mixture is smooth and light`
  - `Alternately add the flour mixture and buttermilk mixture, blending well after each addition`
  - `Fill each cupcake tin with 1/4 cup of batter and bake about 22 minutes`
  - `Cool the cupcakes in the pan for 20 minutes`
  - `Remove cupcakes and cool`
  - `Refrigerate until ready to serve`

### dirty rice.md → dirty-rice.md
- Counts — converted: 15 ing / 12 ins; current: 15 ing / 12 ins
- Per-slug category: **DIVERGENT**
- **Missing in current (converted has, current does not):**
  - `{1} package Zatarians dirty rice mix`
  - `{3} tbsp butter`
- **Extra in current (current has, converted does not):**
  - `{1} package Zatarain's dirty rice mix`
  - `{3} tbsp butter, divided`

### Double Chocolate Chip Cookies.md → double-chocolate-chip-cookies.md
- Counts — converted: 10 ing / 8 ins; current: 11 ing / 9 ins
- Per-slug category: **DIVERGENT**
- **Missing in current (converted has, current does not):**
  - `{10} tablespoons unsalted butter, softened (1 stick plus 2 tablespoons)`
  - `{3/4} cup packed brown sugar`
  - `{1/4} cup granulated sugar`
  - `{1} large egg, room temperature`
  - `{1} cup all-purpose flour, spooned and leveled`
  - `{2/3} cup cocoa powder`
  - `{1 1/4} cup chocolate chips - semi-sweet or dark`
- **Missing instructions in current:**
  - `In a large bowl beat together the butter and sugars together.`
  - `Add the egg and vanilla and continue mixing until combined. Turn off the mixer and scrape down the sides of the bowl.`
  - `Slowly add in the flour, cocoa, baking soda and salt mixing on low speed until incorporated.`
  - `Turn off the electric mixer and stir in the chocolate chips. I usually reserve about 1/4 cup of chocolate chips for sprinkling on top.`
  - `Form dough into balls 3 tablespoons in size and flatten slightly. Place 2 inches apart on a baking sheet lined with parchment paper or a silicon baking mat.`
  - `Cover with cling film and chill in the refrigerator for at least 2 hours or up to 48.`
  - `When ready to bake, preheat the oven to 350F degrees. Bake cookies for 10-12 minutes until the tops are just set.`
  - `Remove from oven and let cool on their tray for 5 minutes before transferring to a wire rack to continue cooling.`
- **Extra in current (current has, converted does not):**
  - `{1} cup ({125} grams) all-purpose flour, spooned and leveled`
  - `{2/3} cup ({60} grams) cocoa powder`
  - `{1 1/2} teaspoons cornstarch (AKA cornflour in the UK and Australia)`
  - `{10} tablespoons ({140} grams) unsalted butter, softened (1 stick plus 2 tablespoons)`
  - `{3/4} cup ({158} grams) packed brown sugar, light or dark`
  - `{1/4} cup ({50} grams) granulated sugar`
  - `{1} large egg`
  - `{1 1/4} cup (about {225} grams) chocolate chips, divided`
- **Extra instructions in current:**
  - `Whisk together the flour, cocoa, baking soda, and salt in a medium bowl. Set aside.`
  - `In a large bowl beat together the butter and sugars until fluffy.`
  - `Add the egg and vanilla into the butter mixture and continue mixing until combined. Turn off the mixer and scrape down the sides of the bowl.`
  - `Slowly mix the dry ingredients into the butter mixture on low speed until incorporated.`
  - `Turn off the electric mixer and stir in {1} cup chocolate chips. Reserve the extra {1/4} cup for dotting on the tops of the cookies.`
  - `Cover the bowl with plastic wrap and chill in the refrigerator for at least 3 hours or up to 48.`
  - `When ready to bake, preheat the oven to 350°F. Line 2 cookie sheets with parchment paper or silicone baking mats. Take the dough out of the fridge and set on the counter for about 15 minutes to warm up slightly if it's been in the fridge overnight.`
  - `Form into balls of 1–1.5 tablespoons in size and place about 1½ inches apart on baking sheets. For larger cookies, form into balls of about 3 tablespoons in size and place 2½ inches (about 6–7 cm) apart.`
  - `Bake cookies for 8–11 minutes (or 12–14 minutes for larger cookies), or until the tops are just set. Remove from oven and let cool on the tray for 10 minutes before transferring to a wire rack to continue cooling. While the cookies are fresh from the oven, optionally dot the tops of each cookie with a few extra chocolate chips.`

### Mrs. Sigg's Snickerdoodles.md → mrs-siggs-snickerdoodles.md
- Counts — converted: 11 ing / 4 ins; current: 11 ing / 8 ins
- Per-slug category: **DIVERGENT**
- **Missing in current (converted has, current does not):**
  - `{2} eggs`
- **Missing instructions in current:**
  - `Preheat oven to 400 degrees F (200 degrees C).`
  - `Cream together butter, shortening, 1 1/2 cups sugar, the eggs and the vanilla. Blend in the flour, cream of tartar, soda and salt. Shape dough by rounded spoonfuls into balls.`
  - `Mix the 2 tablespoons sugar and the cinnamon. Roll balls of dough in mixture. Place 2 inches apart on ungreased baking sheets.`
  - `Bake 8 to 10 minutes, or until set but not too hard. Remove immediately from baking sheets.`
- **Extra in current (current has, converted does not):**
  - `{2} large eggs`
- **Extra instructions in current:**
  - `Preheat the oven to 400°F.`
  - `**Make cookies:** Beat sugar, butter, shortening, eggs, and vanilla in a large bowl until smooth and creamy.`
  - `Whisk flour, cream of tartar, baking soda, and salt together in a separate bowl. Gradually mix dry ingredients mixture into the wet ingredients just until combined.`
  - `Shape dough into walnut-sized balls.`
  - `**Make cinnamon-sugar:** Combine sugar and cinnamon in a small bowl or zip-top plastic bag.`
  - `Place dough balls in cinnamon-sugar and roll or shake until coated. Place 2 inches apart on ungreased baking sheets.`
  - `Bake in the preheated oven until set but not too hard, 8 to 10 minutes, switching racks halfway through.`
  - `Remove from the oven and immediately transfer to wire racks to cool.`

### Pumpkin Cookies.md → pumpkin-drop-cookies.md [title differs: "Pumpkin Cookies" vs "Pumpkin Drop Cookies"]
- Counts — converted: 13 ing / 10 ins; current: 13 ing / 5 ins
- Per-slug category: **DIVERGENT**
- **Missing in current (converted has, current does not):**
  - `{1/2} cup butter, softened`
  - `{3/4} cup sugar`
  - `{3/4} cup brown sugar, packed`
  - `{2} egg`
  - `{15} oz canned pumpkin`
  - `{2 1/2} cup all-purpose flour`
  - `{2 1/2} tsp baking powder`
  - `{1} tsp baking soda`
  - `{1} tsp salt`
  - `{1} tsp cinnamon`
  - `{1} tsp allspice`
  - `{1} tsp nutmeg`
- **Missing instructions in current:**
  - `Heat oven to 375 F`
  - `Grease cookie sheet with shortening`
  - `Mix butter and sugars in large bowl with spoon`
  - `Beat in eggs`
  - `Stir in pumpkin`
  - `Stir in remaining ingredients except raisins`
  - `Fold in raisins`
  - `Bake 10 to 12 minutes or until set and golden`
  - `Cool 1 to 2 minutes; remove from cookie sheet to wire rack`
- **Extra in current (current has, converted does not):**
  - `{1/2} cup butter or margarine, softened`
  - `{3/4} cup granulated sugar`
  - `{3/4} cup packed brown sugar`
  - `{2} eggs`
  - `{1} can (15 ounces) pumpkin (not pumpkin pie mix)`
  - `{2 1/2} cups all-purpose flour`
  - `{2 1/2} teaspoons baking powder`
  - `{1} teaspoon baking soda`
  - `{1} teaspoon salt`
  - `{1} teaspoon ground cinnamon`
  - `{1/4} teaspoon ground allspice`
  - `{1/4} teaspoon ground nutmeg`
- **Extra instructions in current:**
  - `Heat oven to 375°F. Grease cookie sheet with shortening.`
  - `Mix butter and sugars in large bowl with spoon. Beat in eggs one at a time. Stir in pumpkin until well combined.`
  - `Add the dry ingredients to the wet ingredients. Fold in raisins.`
  - `Bake 10 to 12 minutes or until set and golden. Cool 1 to 2 minutes; remove from cookie sheet to wire rack.`

### Raspberry and Almond Shortbread Thumbprints.md → raspberry-thumbprint-cookies.md [title differs: "Raspberry and Almond Shortbread Thumbprints" vs "Raspberry Thumbprint Cookies"]
- Counts — converted: 8 ing / 4 ins; current: 7 ing / 5 ins
- Per-slug category: **DIVERGENT**
- **Missing in current (converted has, current does not):**
  - `{1/2} teaspoon almond extract`
  - `{3/4} teaspoon almond extract`
- **Missing instructions in current:**
  - `Preheat oven to 350 degrees F (175 degrees C).`
  - `In a medium bowl, cream together butter and white sugar until smooth. Mix in 1/2 teaspoon almond extract. Mix in flour until dough comes together. Roll dough into 1 1/2 inch balls, and place on ungreased cookie sheets. Make a small hole in the center of each ball, using your thumb and finger, and fill the hole with preserves.`
  - `Bake for 14 to 18 minutes in preheated oven, or until lightly browned. Let cool 1 minute on the cookie sheet.`
  - `In a medium bowl, mix together the confectioners' sugar, 3/4 teaspoon almond extract, and milk until smooth. Drizzle lightly over warm cookies.`
- **Extra in current (current has, converted does not):**
  - `{1 1/4} teaspoons almond extract, divided`
- **Extra instructions in current:**
  - `Preheat the oven to 350°F.`
  - `Beat butter and white sugar together in a medium bowl until creamy. Mix in {1/2} teaspoon almond extract. Add flour and mix until dough comes together.`
  - `Form dough into 1½-inch balls and place on ungreased cookie sheets about 2 inches apart. Use your thumb to press down and make a dent in the center of each ball, then fill with jam.`
  - `Bake in batches in the preheated oven until edges are lightly browned, about 14 to 18 minutes; allow to cool on cookie sheet for a few minutes.`
  - `Mix confectioners' sugar, milk, and remaining {3/4} teaspoon almond extract together in a medium bowl until smooth; drizzle lightly over warm cookies.`

## NEW (13)

### Brownies.md
- Converted title: "Brownies"
- No matching current recipe.

### chili.md
- Converted title: "Chili"
- No matching current recipe.

### Chocolate Chip Cookies.md
- Converted title: "Award Winning Soft Chocolate Chip Cookies"
- No matching current recipe.

### Crushed Red Pepper Hummus.md
- Converted title: "Crushed Red Pepper Hummus"
- No matching current recipe.

### Dark Chocolate Candy Cane Cookies.md
- Converted title: "Dark Chocolate Candy Cane Cookies"
- No matching current recipe.

### Gingerbread.md
- Converted title: "Gingerbread"
- No matching current recipe.

### Neapolitan Dough.md
- Converted title: "Neapolitan Dough"
- No matching current recipe.

### Pizza Sauce.md
- Converted title: "Pizza Sauce"
- No matching current recipe.

### Red Velvet Crinkle Cookies.md
- Converted title: "Red Velvet Crinkle Cookies"
- No matching current recipe.

### Reese's Stuffed Peanut Butter Cookies.md
- Converted title: "Reese's Stuffed Peanut Butter Cookies"
- No matching current recipe.

### Salsa.md
- Converted title: "Salsa"
- No matching current recipe.

### Sugar Cookies Recipe.md
- Converted title: "Sugar Cookies"
- No matching current recipe.

### Yellow Cake.md
- Converted title: "Yellow Cake"
- No matching current recipe.

## REFERENCE (1)

### Recipes.md
- Converted title: "Cookie Recipes Totals"
- Source is a reference / summary file, not a single recipe.

## MISSING_FILE (0)

_None._
