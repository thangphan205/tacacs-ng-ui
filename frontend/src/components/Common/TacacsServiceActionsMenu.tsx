import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { TacacsServicePublic } from "@/client"
import DeleteTacacsService from "../TacacsServices/DeleteTacacsService"
import EditTacacsService from "../TacacsServices/EditTacacsService"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface TacacsServiceActionsMenuProps {
  tacacs_service: TacacsServicePublic
}

export const TacacsServiceActionsMenu = ({ tacacs_service }: TacacsServiceActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditTacacsService tacacs_service={tacacs_service} />
        <DeleteTacacsService tacacs_service={tacacs_service} />
      </MenuContent>
    </MenuRoot>
  )
}
