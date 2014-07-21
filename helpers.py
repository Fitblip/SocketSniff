AF_Types = {
	0  : "AF_UNSPEC",
	2  : "AF_INET",
	6  : "AF_IPX",
	16 : "AF_APPLETALK",
	17 : "AF_NETBIOS",
	23 : "AF_INET6",
	26 : "AF_IRDA",
	32 : "AF_BTH"
}

Sock_Types = {
	1 : "SOCK_STREAM",
	2 : "SOCK_DGRAM",
	3 : "SOCK_RAW",
	4 : "SOCK_RDM",
	5 : "SOCK_SEQPACKET"
}

Protocol_Types ={
    0   : "NOT_SPECIFIED",
	1   : "IPPROTO_ICMP",
	2   : "IPPROTO_IGMP",
	3   : "BTHPROTO_RFCOMM",
	6   : "IPPROTO_TCP",
	17  : "IPPROTO_UDP",
	58  : "IPPROTO_ICMPV6",
	113 : "IPPROTO_RM"
}
from construct import *

bit9_send_packet = Struct("Bit9Request",
	UNInt32('request_size'),
	UNInt32('number_of_packets_remaining'),
	Bytes('Unknown Data', lambda ctx: ctx.request_size-4)
)
bit9_recv_packet = Struct("Bit9Response",)