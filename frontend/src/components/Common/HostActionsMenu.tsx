import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { HostPublic } from "@/client"
import DeleteHost from "../Hosts/DeleteHost"
import EditHost from "../Hosts/EditHost"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface HostActionsMenuProps {
  host: HostPublic
}

export const HostActionsMenu = ({ host }: HostActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditHost host={host} />
        <DeleteHost host={host} />
      </MenuContent>
    </MenuRoot>
  )
}
