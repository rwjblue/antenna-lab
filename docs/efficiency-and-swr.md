# SWR, loss, and efficiency are different quantities

These terms describe different reference planes or energy conversions and must
not be used interchangeably.

## Transmitter-side SWR

This is what the transmitter sees, usually after the KXAT2. A 1.0:1 result says
the tuner has presented approximately 50 ohms to the radio. It does not prove
that the tuner is lossless, the balanced line is low loss, or the radiator is
efficient.

## Raw feedline input impedance

The RigExpert values are R+jX at the radio end of the deployed 28 ft balanced
line. Raw 50-ohm SWR can be derived from that complex impedance. It describes a
mismatch at that reference plane; by itself it is not an efficiency reading.

## Feedline loss

Feedline efficiency is real power delivered to the modeled radiator load divided
by real power entering the balanced line. Under high standing-wave conditions,
conductor and dielectric loss depend on voltage/current distribution as well as
matched-line attenuation. The optimizer reports this quantity with broad model
uncertainty.

## Radiator efficiency

Radiator efficiency is radiated power divided by power accepted at the radiator
terminals. It includes wire/material and nearby-object losses. It has not been
measured here, and the analytical pattern model normalizes pattern shape rather
than calculating realized gain or radiator efficiency.

## Total realized/radiated system efficiency

For a defined transmitter reference plane, total system efficiency must account
for tuner, choke, feedline, common-mode, radiator, and environmental losses, as
well as any power not accepted at that plane. It cannot be recovered from a
tuner-side SWR or a single R+jX reading alone.

In short: a good transmitter match protects/enables the radio; it does not certify
that most transmitter power is radiated.
