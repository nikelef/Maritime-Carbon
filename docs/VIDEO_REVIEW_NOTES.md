# Maritime Carbon — video review draft

The current review version is an 82-second desktop demonstration with a 30-second
teaser, both with synthetic British English narration. They use fictional vessels,
the actual application and actual calculation results. Intro and closing cards
follow the app's dark teal and light green colours. No video has been posted to LinkedIn.

The visible captions are retained as one layer. The original MP4 contained only
burned-in captions; a player could load the matching SRT alongside them and show
the text twice. Optional subtitle files now live in a separate folder, and the
narrated MP4s contain no additional subtitle stream. The voice is timed to the
existing scenes, and the picture stream is unchanged. The actual spoken text is
included as `Narration_transcript.txt` in the review package.

## What the demonstration shows

- A 2026 decision case containing Demo Atlas and Demo Boreas.
- The assumed EUA price of EUR 85/tCO2e and external pooling price of EUR 190 per tonne of FuelEU compliance balance.
- Atlas's Voyage 1 MGO allocation: 80 tonnes intra-EU and 20 tonnes EU/non-EU, alongside its other entered fuels.
- Boreas's separate Voyage 2 profile, including 300 tonnes of VLSFO on EU/non-EU legs.
- HVO evaluation with a 10% maximum alternative energy share per vessel. The selected quantity can be smaller than that cap.
- Separate FuelEU eligibility and ETS CO2 zero-rating confirmations, with explicitly fictional evidence references.
- The real strategy comparison, selected-leg remarks and CSV/JSON exports.

## Numerical basis of the filmed result

The current-fuel external-pooling option costs EUR 1,218,152.18 in 2026. The
targeted-HVO option costs EUR 1,216,283.69, a modelled reduction of EUR 1,868.49
against that pooling option under the saved assumptions. These figures describe
the same two-vessel case. They are not the earlier one-vessel example.

For Demo Atlas, Voyage 1's intra-EU sea leg replaces 21.876 tonnes/year of MGO
with 21.230 tonnes/year of HVO. For Demo Boreas, Voyage 2's intra-EU sea leg
replaces 8.523 tonnes/year of MGO with 8.271 tonnes/year of HVO. The annual tonnes
shown here are rounded; the audit retains full calculation precision.

Both systems assume equal thermal energy requirements and zero additional
conversion costs. HVO's assumed LCV is 44,000 MJ/t, compared with MGO's 42,700 MJ/t.
Consequently, the alternative and removed fuel masses differ while the replacement
energy stays on the same leg. The case assumes eligible HVO and separately eligible
ETS CO2 treatment. The HSFO entries assume appropriate sulphur-compliance arrangements.

## Optional voiceover draft

Which fuel should a vessel replace, and on which voyage leg?

Maritime Carbon brings fuel, EU ETS and FuelEU costs into one decision case.
Here, two fictional vessels share a 2026 planning horizon.

We enter our allowance and pooling price assumptions, then review each vessel's
annual consumption by voyage, fuel and leg.

Demo Atlas uses MGO on both intra-EU and EU-to-non-EU sea legs. Demo Boreas has
its own operating profile. HVO is evaluated within each vessel's technical limits,
with FuelEU eligibility and ETS zero-rating considered separately.

Now we compare the fleet's options.

In this example, targeted HVO costs around one million two hundred and sixteen
thousand euros for the year—about eighteen hundred and sixty-eight euros less
than the current-fuel pooling option.

The recommendation identifies the ship, voyage, sea leg and replacement tonnes.
The replacement energy stays on that same leg.

Finally, we export the saved inputs and calculations for review.

From annual consumption to a traceable fleet decision. Let's talk about your fleet.

## Draft LinkedIn post

Which fuel, on which voyage leg, at what total cost?

This short Maritime Carbon walkthrough shows how two fictional vessels can be
compared using a common set of FuelEU Maritime and EU ETS planning assumptions.

The result goes beyond a fleet total: it identifies the vessel, voyage leg and
fuel quantity behind the selected strategy, with saved inputs and an exportable
calculation record.

In the illustrative case shown, targeted HVO replacement is EUR 1,868/year below
the current-fuel external-pooling option. Results depend on the fuel, price,
eligibility and technical assumptions entered.

I'd welcome a conversation with fleet analysts and operators about the decisions
they need to compare.

#FuelEU #EUETS #Maritime #Shipping #Decarbonisation

## Production sources

The reproducible workflow is in `scripts/video/README.md`. The video was created
from the desktop app and an isolated fictional database, with Playwright capture
and FFmpeg editing. The app source is https://github.com/nikelef/Maritime-Carbon.
