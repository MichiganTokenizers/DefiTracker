# Kinetic Contract Addresses - FXRP-USDT0-stXRP Pool

## Source
Contract addresses extracted from: [Kinetic Documentation](https://docs.kinetic.market/contracts-and-api-documentation)

## ISO Market: FXRP - USDT0 - STFXRP

### Protocol Contracts
- **Unitroller**: `0x15F69897E6aEBE0463401345543C26d1Fd994abB`
  - Main protocol controller for the ISO market
- **Comptroller Implementation**: `0x35aFf580e53d9834a3a0e21a50f97b942Aba8866`
  - Comptroller logic implementation
- **Lens**: `0x553e7b78812D69fA30242E7380417781125C7AC7`
  - Read-only contract for querying market data (supply rates, borrow rates, etc.)

### Token Contracts
- **FXRP Token**: `0xAd552A648C74D49E10027AB8a618A3ad4901c5bE`
- **ISO FXRP Market**: `0xD1b7A5eFa9bd88F291F7A4563a8f6185c0249CB3`
  - Lending market contract for FXRP

- **USDT0 Token**: `0xe7cd86e13AC4309349F30B3435a9d337750fC82D`
- **ISO USDT0 Market**: `0xad7e7989796414c9572da9854DEb1B920724fd09`
  - Lending market contract for USDT0

- **STFXRP Token**: `0x4C18Ff3C89632c3Dd62E796c0aFA5c07c4c1B2b3`
- **isoSTFXRP Market**: `0x870f7B89F0d408D7CA2E6586Df26D00Ea03aA358`
  - Lending market contract for stXRP

## Implementation Notes

### Method 1: Current APR from Lens Contract
The Lens contract (`0x553e7b78812D69fA30242E7380417781125C7AC7`) provides read-only access to current market data. We can query:
- Current supply rate per block
- Total supply
- Total borrows
- Market state

**Next Step**: Get Lens contract ABI to implement `_get_apr_from_lens()`

### Method 2: Historical APR from Events
Query historical events from:
- **Comptroller**: Reward distribution events
- **ISO Market Contracts**: Supply/deposit events (Mint events)

**Next Step**: Get contract ABIs and event signatures

## API Status
**Kinetic does NOT provide REST API endpoints**. All data must be queried on-chain via:
1. Lens contract (for current state)
2. Direct contract calls (for historical data)
3. Event logs (for historical calculations)

## Configuration
All addresses have been added to `config/chains.yaml`:
- Unitroller, Comptroller, and Lens addresses
- Token addresses (FXRP, USDT0, stXRP)
- ISO market addresses for each token

