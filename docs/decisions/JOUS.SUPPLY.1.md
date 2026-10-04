\# JOUS.SUPPLY.1 — MVP Supply Architecture \& Supplier Decision



\*\*Status:\*\* APPROVED FOR MVP  

\*\*Date:\*\* 2026-10-03  

\*\*Repository:\*\* anoopkundra/jous  

\*\*Decision Class:\*\* Architecture / AI Supply  

\*\*Supersedes:\*\* Initial single-gateway assumptions



\---



\## 1. Purpose



This document defines how Jous acquires, selects, routes, measures, and replaces AI inference supply for the MVP.



Jous must not become dependent on any individual AI gateway, aggregator, inference provider, or model provider.



The architectural rule is:



> \*\*NO AI SUPPLIER DEPENDENCY ABOVE THE ADAPTER BOUNDARY.\*\*



Jous owns the economic relationship with the customer.



Gateways and inference providers are replaceable supply infrastructure.



\---



\## 2. Product Principle



Jous is not being built as another generic AI gateway.



The gateway is infrastructure.



Jous's differentiated intellectual property is expected to reside primarily in:



\- Jous Ledger

\- Jous Balance

\- Spend Intelligence

\- Project Economics

\- Rewards Engine

\- Customer Economic Profile

\- Jous Model Registry

\- Jous Economic Router

\- Effective-Cost Optimization

\- Rewards Marketplace

\- Aggregated AI purchasing intelligence



The governing product question is:



> \*\*How should your next AI dollar be spent?\*\*



\---



\## 3. Architecture Decision



The MVP will use a supplier-neutral architecture.



```text

Jous Workspace / Jous API

&#x20;           |

&#x20;           v

&#x20;    Jous Control Plane

&#x20;   +--------------------+

&#x20;   | Identity           |

&#x20;   | Projects           |

&#x20;   | Wallet / Ledger    |

&#x20;   | Spend Intelligence |

&#x20;   | Rewards            |

&#x20;   +---------+----------+

&#x20;             |

&#x20;             v

&#x20;     Jous Economic Router

&#x20;             |

&#x20;      Jous Model Registry

&#x20;             |

&#x20;    +--------+--------+

&#x20;    |        |        |

&#x20;    v        v        v

&#x20;   HF     OpenRouter Vercel

&#x20; Adapter    Adapter   Adapter

&#x20;    |        |        |

&#x20;    +--------+--------+

&#x20;             |

&#x20;             v

&#x20;    Actual AI Providers

