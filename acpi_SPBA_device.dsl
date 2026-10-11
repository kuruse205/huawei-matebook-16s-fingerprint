    Scope (_SB.PC00.SPI0)
    {
        Device (SPBA)
        {
            Name (_ADR, Zero)  // _ADR: Address
            Name (_HID, "GDIX51C0")  // _HID: Hardware ID
            Name (_CID, "GDIX51C0")  // _CID: Compatible ID
            Name (_UID, One)  // _UID: Unique ID
            Name (SID0, One)
            If (Ones)
            {
                SID0 = GGIV (0x0902000C)
                If ((SID0 == Zero))
                {
                    _HID = "SIL6150"
                    _CID = "SIL6150"
                }
            }

            Method (_INI, 0, NotSerialized)  // _INI: Initialize
            {
                SHPO (0x090E0001, One)
                SHPO (0x0907000C, One)
            }

            Method (_STA, 0, NotSerialized)  // _STA: Status
            {
                If (HFTE)
                {
                    Return (0x0F)
                }

                Return (Zero)
            }

            Method (_CRS, 0, Serialized)  // _CRS: Current Resource Settings
            {
                Name (RBUF, ResourceTemplate ()
                {
                    SpiSerialBusV2 (0x0000, PolarityLow, FourWireMode, 0x08,
                        ControllerInitiated, 0x00989680, ClockPolarityLow,
                        ClockPhaseFirst, "\\_SB.PC00.SPI0",
                        0x00, ResourceConsumer, _Y78, Exclusive,
                        )
                    GpioInt (Level, ActiveHigh, ExclusiveAndWake, PullDefault, 0x0000,
                        "\\_SB.GPI0", 0x00, ResourceConsumer, ,
                        )
                        {   // Pin list
                            0x0000
                        }
                    GpioIo (Exclusive, PullUp, 0x0000, 0x0000, IoRestrictionOutputOnly,
                        "\\_SB.GPI0", 0x00, ResourceConsumer, ,
                        )
                        {   // Pin list
                            0x0000
                        }
                })
                CreateWordField (RBUF, \_SB.PC00.SPI0.SPBA._CRS._Y78._SPE, FREQ)  // _SPE: Speed
                If ((SID0 == Zero))
                {
                    FREQ = 0x005B8D80
                }

                CreateWordField (RBUF, 0x3B, GPIN)
                CreateWordField (RBUF, 0x5E, SPIN)
                GPIN = GNUM (0x090E0001)
                SPIN = GNUM (0x0907000C)
                Return (RBUF) /* \_SB_.PC00.SPI0.SPBA._CRS.RBUF */
            }
        }
