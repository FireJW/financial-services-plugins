# Policy Pressure And Pivot Risk

Use this reference when the macro question depends on whether a political
leader, especially Donald Trump, is likely to retreat, delay, soften, or
repackage a policy after market or political stress.

This is a pressure overlay, not a truth engine.

## What The Image Most Likely Implies

Based on the caption shown in the image, the Deutsche Bank pressure index is
most likely built from an equally weighted set of short-horizon changes in:

1. `S&P 500`
2. `10-year U.S. Treasury yield`
3. `Trump approval rate`
4. `1-year forward inflation`

The caption implies a `20-day change` for each component.

## Likely Sign Convention

To make a higher reading mean more pressure on Trump to pivot, the most likely
direction is:

1. `S&P 500`
   - lower equities = more pressure
   - practical sign in the composite: `negative`
2. `10-year U.S. Treasury yield`
   - higher long yields = more pressure
   - practical sign in the composite: `positive`
3. `Trump approval rate`
   - lower approval = more pressure
   - practical sign in the composite: `negative`
4. `1-year forward inflation`
   - higher inflation expectations = more pressure
   - practical sign in the composite: `positive`

In plain terms:

- stocks down
- yields up
- approval down
- inflation expectations up

should push the index higher.

## Likely Construction Variants

Because the four inputs use different units, the bank almost certainly did not
just add raw changes together without normalization.

The most plausible implementations are:

### Variant A: equally weighted standardized changes

```text
Pressure_t
= 0.25 * z(-Δ20d S&P500)
+ 0.25 * z(+Δ20d 10y yield)
+ 0.25 * z(-Δ20d approval)
+ 0.25 * z(+Δ20d 1y inflation expectations)
```

This is the cleanest version and the most likely default.

### Variant B: equally weighted percentile or volatility-normalized changes

```text
Pressure_t
= average(
  scaled(-Δ20d S&P500),
  scaled(+Δ20d 10y yield),
  scaled(-Δ20d approval),
  scaled(+Δ20d 1y inflation expectations)
)
```

This is almost as plausible if the bank wanted a more stable chart.

## Why The Big Spikes Make Sense

### April 2025 tariff retreat

The composite should spike if:

- equities sold off
- yields rose instead of falling
- inflation expectations rose on tariff fears
- approval softened

That is the classic `policy retreat under market and stagflation pressure`
setup.

### March 2026 Iran-war spike

The composite should spike if:

- war risk pushed oil and inflation expectations higher
- Treasury yields rose on inflation or fiscal stress
- equities weakened
- approval came under pressure

That combination raises the odds of rhetorical moderation, delay,
carve-outs, or partial backtracking even if the administration does not fully
reverse course.

## How To Use It In Macro Notes

Use this composite as a `pivot-risk overlay`.

Do:

1. write the factual macro note first
2. decide what is confirmed
3. decide what is scenario-only
4. then add the pressure overlay to judge whether policy hard lines are likely
   to soften

Do not:

1. use the pressure index as proof that a pivot is already happening
2. use it without separating `market stress` from `policy reversal`
3. let it overwrite hard evidence from official statements or actions

## Practical Read Rules

### Higher and rising

- growing odds of delay, softer rhetoric, narrower scope, exemptions, or a
  tactical reset

### High but flattening

- pressure is already elevated, but the pivot may already be priced or partly
  underway

### Falling after a concession

- pressure may be easing because the political system has already responded

## False Positives

Watch these carefully:

1. `risk-off yields falling`
   - if stocks fall but yields also fall sharply, the pressure story is less
     clean than a bond-vigilante setup
2. `poll lag`
   - approval data often lags the market
3. `inflation-expectation noise`
   - survey-based inflation moves can overreact for short periods
4. `war premium without domestic political pain`
   - external conflict can raise inflation expectations before approval damage
     becomes visible

## Recommended Output Fields

When this overlay is relevant, add:

- `policy_pressure_overlay`
- `pressure_components`
- `pressure_signals_aligned`
- `pivot_risk_read`
- `what_would_raise_pivot_odds`
- `what_would_reduce_pivot_odds`

## Best Use Cases

- Trump tariff retreat probability
- Trump sanctions carve-out probability
- White House tone-reset probability after market stress
- tactical `TACO`-style reversal risk in a live macro note
