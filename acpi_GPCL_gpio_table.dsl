        Name (GPCL, Package (0x12)
        {
            Package (0x09)
            {
                0x006E0000, 
                0x1A, 
                0x0700, 
                0xB0, 
                0x20, 
                0x0140, 
                0x80, 
                0x84, 
                Zero
            }, 

            Package (0x09)
            {
                0x006E0000, 
                0x10, 
                0x08A0, 
                0xB4, 
                0x30, 
                0x0144, 
                0x88, 
                0x8C, 
                0x20
            }, 

            Package (0x09)
            {
                0x006E0000, 
                0x19, 
                0x09A0, 
                0xB8, 
                0x38, 
                0x0148, 
                0x90, 
                0x94, 
                0x40
            }, 

            Package (0x09)
            {
                0x00690000, 
                0x08, 
                0x0700, 
                0xB0, 
                0x20, 
                0x0140, 
                0x80, 
                0x84, 
                0x0160
            }, 

            Package (0x09)
            {
                0x00690000, 
                0x09, 
                0x0780, 
                0xB4, 
                0x24, 
                0xFFFF, 
                0x88, 
                0x8C, 
                0xFFFF
            }, 

            Package (0x09)
            {
                0x006C0000, 
                0x11, 
                0x0700, 
                0xB0, 
                0x20, 
                0x0140, 
                0x80, 
                0x84, 
                0xFFFF
            }, 

            Package (0x09)
            {
                0x006D0000, 
                0x08, 
                0x0700, 
                0xB0, 
                0x20, 
                0x0140, 
                0x80, 
                0x84, 
                0x60
            }, 

            Package (0x09)
            {
                0x006D0000, 
                0x18, 
                0x0780, 
                0xB4, 
                0x24, 
                0x0144, 
                0x88, 
                0x8C, 
                0x80
            }, 

            Package (0x09)
            {
                0x006D0000, 
                0x15, 
                0x0900, 
                0xB8, 
                0x30, 
                0x0148, 
                0x90, 
                0x94, 
                0xA0
            }, 

            Package (0x09)
            {
                0x006D0000, 
                0x18, 
                0x0A50, 
                0xBC, 
                0x3C, 
                0x014C, 
                0x98, 
                0x9C, 
                0xC0
            }, 

            Package (0x09)
            {
                0x006D0000, 
                0x1D, 
                0x0BD0, 
                0xC0, 
                0x48, 
                0x0150, 
                0xA0, 
                0xA4, 
                0xE0
            }, 

            Package (0x09)
            {
                0x006A0000, 
                0x18, 
                0x0700, 
                0xB0, 
                0x20, 
                0x0140, 
                0x80, 
                0x84, 
                0x0100
            }, 

            Package (0x09)
            {
                0x006A0000, 
                0x19, 
                0x0880, 
                0xB4, 
                0x2C, 
                0x0144, 
                0x88, 
                0x8C, 
                0x0120
            }, 

            Package (0x09)
            {
                0x006A0000, 
                0x06, 
                0x0A10, 
                0xB8, 
                0x3C, 
                0xFFFF, 
                0x90, 
                0x94, 
                0xFFFF
            }, 

            Package (0x09)
            {
                0x006A0000, 
                0x19, 
                0x0A70, 
                0xBC, 
                0x40, 
                0x014C, 
                0x98, 
                0x9C, 
                0x0140
            }, 

            Package (0x09)
            {
                0x006A0000, 
                0x0A, 
                0x0C00, 
                0xC0, 
                0x50, 
                0xFFFF, 
                0xA0, 
                0xA4, 
                0xFFFF
            }, 

            Package (0x09)
            {
                0x006B0000, 
                0x0F, 
                0x0700, 
                0xB0, 
                0x20, 
                0xFFFF, 
                0x80, 
                0x84, 
                0xFFFF
            }, 

            Package (0x09)
            {
                0x006B0000, 
                0x5B, 
                0x07F0, 
                0xB4, 
                0x28, 
                0xFFFF, 
                0x88, 
                0x8C, 
                0xFFFF
            }
        })
        Name (RXEV, Package (0x12)
        {
            Buffer (0x1A){}, 
            Buffer (0x10){}, 
            Buffer (0x19){}, 
            Buffer (0x08){}, 
            Buffer (0x09){}, 
            Buffer (0x11){}, 
            Buffer (0x08){}, 
            Buffer (0x18){}, 
            Buffer (0x15){}, 
            Buffer (0x18){}, 
            Buffer (0x1D){}, 
            Buffer (0x18){}, 
            Buffer (0x19){}, 
            Buffer (0x06){}, 
            Buffer (0x19){}, 
            Buffer (0x0A){}, 
            Buffer (0x0F){}, 
            Buffer (0x5B){}
        })
    }

    Scope (_SB)
    {
        Method (GINF, 2, NotSerialized)
        {
            Return (DerefOf (DerefOf (GPCL [Arg0]) [Arg1]))
        }

        Method (GMXG, 0, NotSerialized)
        {
            Return (0x12)
        }
    }

